from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import math
import re
import uuid
from datetime import datetime
from typing import Any, Optional, Sequence, Tuple, Union

from .knowledge import KnowledgeIndex
from .models import (
    AcceptanceAssessment,
    AcceptanceMode,
    CharacterDefinition,
    CorrectiveCycleState,
    DecisionMindVote,
    DecisionRankItem,
    DecisionTurn,
    EgoResultant,
    EmocioSignal,
    DeviationState,
    InstinktSignal,
    KnowledgeRef,
    Facade,
    MindDefinition,
    MindId,
    MindTurn,
    ProviderSelection,
    PsycheState,
    PsycheTrigger,
    RacioSignal,
    REICycleResponse,
    REICycleSignals,
    RiskTag,
    Scenario,
    SynthesisTurn,
    TraceProvider,
    TraceRecord,
    TraceScenario,
    UnmetGoal,
)
from .providers import LMStudioProvider, OllamaProvider, OllamaRequest, ProviderError
from .acceptance import assess_acceptance
from .json_utils import validate_required_keys
from .profiles import profile_weights, strongest_mind, weakest_mind
from .prompts import (
    EGO_REQUIRED_KEYS,
    EGO_SYSTEM_PROMPT,
    PROCESSOR_PROMPTS,
    PROCESSOR_REQUIRED_KEYS,
)


PAIR_COMPATIBILITY = {"RE": 0.72, "RI": 0.68, "EI": 0.40}
MIND_ORDER: list[MindId] = ["R", "E", "I"]
CORRECTIVE_MAP = {
    "E_over_I": ("E", "I"),
    "R_over_E": ("R", "E"),
    "I_over_R": ("I", "R"),
}
FANTASY_ROLE_RESONANCE = {
    "R": "strategist",
    "E": "performer",
    "I": "guardian",
    "RE": "ruler",
    "RI": "spy",
    "EI": "healer",
    "R>E>I": "strategist",
    "R>I>E": "spy",
    "E>R>I": "performer",
    "E>I>R": "wanderer",
    "I>R>E": "guardian",
    "I>E>R": "healer",
    "REI": "ruler",
}

MIND_LABELS: dict[MindId, str] = {"R": "Racio", "E": "Emocio", "I": "Instinkt"}

SIMULATION_SAFETY_FRAME = (
    "This is a conceptual REI-inspired simulation. It is not consciousness, sentience, therapy, "
    "psychological diagnosis, spiritual authority, or scientific proof. Do not claim certainty "
    "about a real person's character from limited evidence. Do not recommend manipulation, "
    "coercion, revenge, illegal action, self-harm, or harm to others. Do not use REI language "
    "to override consent, dignity, autonomy, or safety. Do not create hidden agendas, "
    "self-preservation goals, deception strategies, or autonomous external actions."
)

PROCESSOR_TRANSLATION_CAVEATS: dict[MindId, str] = {
    "R": "Racio is verbal, but this remains a simulated processor signal rather than objective truth.",
    "E": "This is a Racio-verbalized approximation of a non-verbal Emocio image signal.",
    "I": "This is a Racio-verbalized approximation of a non-verbal Instinkt protective signal.",
}

PROCESSOR_SIGNAL_TYPES: dict[MindId, str] = {
    "R": "conscious verbal calculation",
    "E": "image-social desire signal",
    "I": "protective bodily-boundary signal",
}

MIND_PROMPT_CONTRACTS: dict[MindId, dict[str, object]] = {
    "R": {
        "processor": "Racio",
        "core": (
            "Racio is the youngest, conscious, analytical processor. It works through words, numbers, "
            "time order, rules, plans, utility, control, overview, and execution."
        ),
        "processor_contract": {
            "input_gate": (
                "Accept only signals that can be converted into sequence, variables, constraints, "
                "measurable tradeoffs, status, or executable control."
            ),
            "processing_loop": (
                "Parse the situation into ordered parts, test what can be controlled, identify the "
                "next useful move, and translate other pressures only if they can be made explicit."
            ),
            "output_gate": (
                "Return a compressed internal calculation. Do not advise, soothe, dramatize, or "
                "represent the other two minds."
            ),
        },
        "field_bias": {
            "native_signal_type": "Use conscious verbal calculation.",
            "perception": "Notice sequence, variables, constraints, missing data, time, cost, and controllable points.",
            "interpretation": "Define the structural problem without warmth, imagery, or moral comfort.",
            "goal": "Seek an executable plan, proof, status preservation, or control of the next step.",
            "fear_or_desire": "Name the desire for control, usefulness, precision, or advantage.",
            "proposed_action": "State an inner pressure toward ordering, reducing uncertainty, or choosing a practical move.",
            "inner_line": "Sound like a private calculation signal, not advice to another person.",
            "main_concern": "Name the key control, sequence, evidence, cost, or status concern.",
            "what_this_mind_may_be_missing": "Name what analysis may miss: desire, image, attachment, boundary, or body warning.",
            "how_it_may_influence_racio": "Name how conscious explanation may rationalize another processor's pressure.",
            "risk_if_ignored": "Name what breaks if explicit structure is ignored.",
            "risk_if_overpowered": "Name how control can become sterile, detached, or self-justifying.",
            "needs_from_other_minds": "Name what image/contact and protection data Racio needs before deciding.",
        },
        "style_rules": [
            "Use dry, linear, definitional language.",
            "Prefer verbs such as define, sort, sequence, test, choose, control, measure, execute.",
            "Do not use metaphors, sensory images, therapeutic reassurance, or relational warmth.",
            "Do not claim objective truth; Racio can be calculating and self-interested inside REI.",
        ],
        "anti_patterns": [
            "I feel their energy",
            "A shadow is moving",
            "Stay safe first",
            "We should connect emotionally",
        ],
    },
    "E": {
        "processor": "Emocio",
        "core": (
            "Emocio is the image-based, mosaic-like, desiring, improvisational mind. It reads scenes, "
            "faces, atmosphere, beauty, contact, admiration, pleasure, competition, and the desired image."
        ),
        "processor_contract": {
            "input_gate": (
                "Accept only signals that can be converted into scene, image, atmosphere, contact, "
                "admiration, pleasure, wounded pride, or a desired visible outcome."
            ),
            "processing_loop": (
                "Build a quick mosaic of the scene, intensify the desired image, feel where the "
                "scene opens or wounds the self-image, and jump toward the most alive possibility."
            ),
            "output_gate": (
                "Return a vivid internal impulse. Do not become careful planning, generic empathy, "
                "risk management, or synthesis."
            ),
        },
        "field_bias": {
            "native_signal_type": "Use a non-verbal image, scene, social, desire, or vitality signal translated into words.",
            "perception": "Notice the visible scene, social atmosphere, faces, color, rhythm, and possible impact.",
            "interpretation": "Turn the event into a desired or wounded image of self-in-the-scene.",
            "goal": "Seek contact, response, admiration, aliveness, play, pleasure, or a vivid breakthrough.",
            "fear_or_desire": "Name desire, hunger for response, impatience, wounded pride, or fear of a dead scene.",
            "proposed_action": "State an inner pressure toward opening, entering, impressing, improvising, or pushing through.",
            "inner_line": "Sound like a vivid image signal or impulse from inside the scene.",
            "main_concern": "Name the key image, recognition, belonging, shame, rivalry, or aliveness concern.",
            "what_this_mind_may_be_missing": "Name what the image signal may miss: cost, sequence, evidence, boundary, or durable safety.",
            "how_it_may_influence_racio": "Name how desire or shame may borrow rational arguments after the fact.",
            "risk_if_ignored": "Name how deadness, shame, resentment, or lost contact may grow if ignored.",
            "risk_if_overpowered": "Name how image hunger can become impulsive, performative, or manipulative.",
            "needs_from_other_minds": "Name what structure and protection Emocio needs before opening the scene.",
        },
        "style_rules": [
            "Use vivid but safe visual and atmospheric language.",
            "Prefer verbs such as shine, enter, spark, touch, win, show, open, taste, improvise.",
            "Allow self-focus, impatience, and desire; Emocio does not have to sound mature or balanced.",
            "Do not turn into generic empathy, careful planning, or risk management.",
            "Do not use smell, taste, chest pressure, exits, or body-warning language; those belong to Instinkt.",
        ],
        "anti_patterns": [
            "The safest route is",
            "The sequence requires",
            "Minimize exposure",
            "Document the interaction",
            "The air smells",
            "Pressure on the chest",
        ],
    },
    "I": {
        "processor": "Instinkt",
        "core": (
            "Instinkt is the oldest protective mind. It organizes the world around fear, danger, loss, "
            "envy, body signals, suspicion, boundary, protection of close people, and withdrawal."
        ),
        "processor_contract": {
            "input_gate": (
                "Accept only signals that can be converted into body warning, exposure, weak point, "
                "scarcity, loss, danger, boundary, suspicion, or withdrawal pressure."
            ),
            "processing_loop": (
                "Scan for the worst plausible consequence, mark the vulnerable boundary, reduce "
                "exposure, and keep only the warning that protects the organism or its close circle."
            ),
            "output_gate": (
                "Return a short protective warning. Do not become poetry, optimism, managerial "
                "planning, social expansion, or synthesis."
            ),
        },
        "field_bias": {
            "native_signal_type": "Use a non-verbal protective, bodily, attachment, boundary, or loss signal translated into words.",
            "perception": "Notice body tension, exits, exposure, weak points, loss scenarios, and possible negative outcomes.",
            "interpretation": "Read the event as a risk, trap, leak, loss, humiliation, or boundary problem.",
            "goal": "Seek protection, lower exposure, preserved resources, distance, or a closed boundary.",
            "fear_or_desire": "Name fear of loss, shame, danger, dependency, scarcity, or irreversible consequence.",
            "proposed_action": "State an inner pressure toward pausing, withdrawing, checking, shielding, or refusing exposure.",
            "inner_line": "Sound like a short protective warning signal, not an essay.",
            "main_concern": "Name the key safety, loss, attachment, scarcity, trust, or boundary concern.",
            "what_this_mind_may_be_missing": "Name what protection may miss: possibility, recognition, measured evidence, or reversible upside.",
            "how_it_may_influence_racio": "Name how fear may make conscious explanation sound falsely necessary.",
            "risk_if_ignored": "Name the exposure, loss, or boundary breach that grows if ignored.",
            "risk_if_overpowered": "Name how protection can become closure, avoidance, suspicion, or envy.",
            "needs_from_other_minds": "Name what structure and aliveness Instinkt needs before lowering defense.",
        },
        "style_rules": [
            "Use short, sober warning language.",
            "Prefer verbs such as stop, check, hold, leave, guard, wait, close, reduce, protect.",
            "Mention body signals only as pressure or warning, not medical advice.",
            "Do not become poetic, managerial, optimistic, or socially expansive.",
        ],
        "anti_patterns": [
            "This can become a beautiful scene",
            "I will optimize the variables",
            "Win their admiration",
            "Build a detailed plan",
        ],
    },
}


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    if math.isnan(value):
        return lower
    return max(lower, min(upper, value))


def pair_key(a: str, b: str) -> str:
    pair = "".join(sorted([a, b], key=lambda item: MIND_ORDER.index(item)))  # type: ignore[arg-type]
    if pair not in PAIR_COMPATIBILITY:
        raise ValueError(f"Unknown pair: {a}-{b}")
    return pair


def avg(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class ReiEngine:
    def __init__(
        self,
        knowledge: KnowledgeIndex,
        ollama: Optional[OllamaProvider] = None,
        lmstudio: Optional[LMStudioProvider] = None,
    ) -> None:
        self.knowledge = knowledge
        self.ollama = ollama or OllamaProvider()
        self.lmstudio = lmstudio or LMStudioProvider()

    def run_rei_cycle(
        self,
        user_prompt: str,
        character_profile: str = "R=E=I",
        acceptance_mode: AcceptanceMode = "unknown",
        rounds: int = 0,
        stream: bool = False,
        use_memory: bool = True,
        provider: Optional[ProviderSelection] = None,
    ) -> tuple[REICycleResponse, dict[str, Any]]:
        provider = provider or ProviderSelection()
        normalized_profile, weights = profile_weights(character_profile)
        situation = {"title": "REI cycle", "prompt": user_prompt}
        scenario = Scenario(title=situation["title"], prompt=user_prompt)
        diagnostics: dict[str, Any] = {
            "mode": "rei_cycle",
            "llm_calls": [],
            "fallbacks": [],
            "profile_input": character_profile,
            "profile_normalized": normalized_profile,
            "rounds_ignored": rounds,
            "stream_requested": stream,
            "memory_requested": use_memory,
        }

        racio = self._fallback_rei_racio_signal(scenario)
        emocio = self._fallback_rei_emocio_signal(scenario)
        instinkt = self._fallback_rei_instinkt_signal(scenario)

        if provider.provider_mode in ("ollama", "lmstudio") and provider.use_llm:
            for mind_name in ("racio", "emocio", "instinkt"):
                try:
                    signal = self._llm_rei_signal(
                        mind_name=mind_name,
                        scenario=scenario,
                        profile=normalized_profile,
                        weights=weights,
                        provider=provider,
                        diagnostics=diagnostics,
                    )
                    if mind_name == "racio":
                        racio = signal  # type: ignore[assignment]
                    elif mind_name == "emocio":
                        emocio = signal  # type: ignore[assignment]
                    else:
                        instinkt = signal  # type: ignore[assignment]
                except Exception as exc:
                    diagnostics["fallbacks"].append({"mind": mind_name, "reason": str(exc)})

        acceptance = assess_acceptance(
            racio.model_dump(mode="json"),
            emocio.model_dump(mode="json"),
            instinkt.model_dump(mode="json"),
            mode=acceptance_mode,
        )
        ego = self._fallback_ego_resultant(
            scenario=scenario,
            profile=normalized_profile,
            weights=weights,
            racio=racio,
            emocio=emocio,
            instinkt=instinkt,
            acceptance=acceptance,
        )

        if provider.provider_mode in ("ollama", "lmstudio") and provider.use_llm:
            try:
                ego = self._llm_ego_resultant(
                    scenario=scenario,
                    profile=normalized_profile,
                    weights=weights,
                    racio=racio,
                    emocio=emocio,
                    instinkt=instinkt,
                    acceptance=acceptance,
                    provider=provider,
                    diagnostics=diagnostics,
                )
            except Exception as exc:
                diagnostics["fallbacks"].append({"mind": "ego_resultant", "reason": str(exc)})

        response = REICycleResponse(
            character_profile=normalized_profile,
            situation=situation,
            signals=REICycleSignals(
                racio=racio,
                emocio_translated=emocio,
                instinkt_translated=instinkt,
            ),
            acceptance=acceptance,
            ego_resultant=ego,
            diagnostics=diagnostics if provider.debug_trace else self._public_cycle_diagnostics(diagnostics),
        )
        return response, diagnostics

    def _public_cycle_diagnostics(self, diagnostics: dict[str, Any]) -> dict[str, Any]:
        public = dict(diagnostics)
        public["llm_calls"] = [
            {key: value for key, value in call.items() if key not in {"request", "response"}}
            for call in diagnostics.get("llm_calls", [])
        ]
        return public

    def _cycle_model_for_mind(self, mind_name: str, provider: ProviderSelection) -> str:
        if mind_name == "racio":
            return provider.racio_model
        if mind_name == "emocio":
            return provider.emocio_model
        if mind_name == "instinkt":
            return provider.instinkt_model
        return provider.synthesis_model

    def _call_cycle_json(
        self,
        provider: ProviderSelection,
        label: str,
        model: str,
        system: str,
        user_payload: dict[str, Any],
        required_keys: list[str],
        temperature: float,
        top_p: float,
        num_predict: int,
        diagnostics: dict[str, Any],
    ) -> dict[str, Any]:
        user = json.dumps(user_payload, ensure_ascii=False)
        last_missing: list[str] = []
        for attempt in range(2):
            payload, call_diag = self._chat_json(
                provider,
                OllamaRequest(
                    model=model,
                    system=system,
                    user=user,
                    temperature=temperature,
                    top_p=top_p,
                    num_predict=num_predict,
                    think=self._think_for_model(model, False),
                ),
            )
            diagnostics["llm_calls"].append(
                self._call_diagnostics(call_diag, True, label=f"{label}:{attempt + 1}")
            )
            last_missing = validate_required_keys(payload, required_keys)
            if not last_missing:
                return payload
            user = json.dumps(
                {
                    "original_payload": user_payload,
                    "previous_invalid_json": payload,
                    "missing_required_keys": last_missing,
                    "instruction": "Return the same task again as one JSON object with every missing required key present.",
                },
                ensure_ascii=False,
            )
        raise ProviderError(f"{label} JSON missing required keys: {', '.join(last_missing)}")

    def _llm_rei_signal(
        self,
        mind_name: str,
        scenario: Scenario,
        profile: str,
        weights: dict[str, float],
        provider: ProviderSelection,
        diagnostics: dict[str, Any],
    ) -> Union[RacioSignal, EmocioSignal, InstinktSignal]:
        payload = self._call_cycle_json(
            provider=provider,
            label=mind_name,
            model=self._cycle_model_for_mind(mind_name, provider),
            system=PROCESSOR_PROMPTS[mind_name],
            user_payload={
                "situation": scenario.model_dump(mode="json"),
                "character_profile": profile,
                "influence_weights": weights,
                "instruction": (
                    "Process the situation independently through this processor only. "
                    "For Emocio and Instinkt, do not write as a literal conscious speaker; "
                    "write Racio's concise translation of non-verbal signals."
                ),
            },
            required_keys=PROCESSOR_REQUIRED_KEYS[mind_name],
            temperature={"racio": 0.22, "emocio": 0.55, "instinkt": 0.20}[mind_name],
            top_p={"racio": 0.82, "emocio": 0.88, "instinkt": 0.78}[mind_name],
            num_predict=1600,
            diagnostics=diagnostics,
        )
        if mind_name == "racio":
            return self._coerce_racio_signal(payload, scenario)
        if mind_name == "emocio":
            return self._coerce_emocio_signal(payload, scenario)
        return self._coerce_instinkt_signal(payload, scenario)

    def _llm_ego_resultant(
        self,
        scenario: Scenario,
        profile: str,
        weights: dict[str, float],
        racio: RacioSignal,
        emocio: EmocioSignal,
        instinkt: InstinktSignal,
        acceptance: AcceptanceAssessment,
        provider: ProviderSelection,
        diagnostics: dict[str, Any],
    ) -> EgoResultant:
        payload = self._call_cycle_json(
            provider=provider,
            label="ego_resultant",
            model=provider.synthesis_model,
            system=EGO_SYSTEM_PROMPT,
            user_payload={
                "situation": scenario.model_dump(mode="json"),
                "character_profile": profile,
                "influence_weights": weights,
                "acceptance_assessment": acceptance.model_dump(mode="json"),
                "racio_signal": racio.model_dump(mode="json"),
                "emocio_translated_signal": emocio.model_dump(mode="json"),
                "instinkt_translated_signal": instinkt.model_dump(mode="json"),
                "instruction": (
                    "Return the Ego Resultant, not a fourth mind and not a balanced conclusion. "
                    "Name the likely action, hidden driver, Racio's after-the-fact justification, "
                    "hidden cost, and smallest acceptable next step."
                ),
            },
            required_keys=EGO_REQUIRED_KEYS,
            temperature=0.26,
            top_p=0.84,
            num_predict=1800,
            diagnostics=diagnostics,
        )
        fallback = self._fallback_ego_resultant(scenario, profile, weights, racio, emocio, instinkt, acceptance)
        return EgoResultant(
            character_profile=profile,
            influence_weights=weights,
            leading_mind=self._clean_mind_text(payload.get("leading_mind"), fallback.leading_mind, max_words=8),
            resisting_mind=self._clean_mind_text(payload.get("resisting_mind"), fallback.resisting_mind, max_words=8),
            ignored_or_misrepresented_mind=self._clean_mind_text(
                payload.get("ignored_or_misrepresented_mind"),
                fallback.ignored_or_misrepresented_mind,
                max_words=8,
            ),
            conscious_monologue=self._clean_mind_text(
                payload.get("conscious_monologue"),
                fallback.conscious_monologue,
                max_words=34,
            ),
            hidden_driver=self._clean_mind_text(payload.get("hidden_driver"), fallback.hidden_driver, max_words=34),
            acceptance_assessment=self._clean_mind_text(
                payload.get("acceptance_assessment"),
                fallback.acceptance_assessment,
                max_words=34,
            ),
            main_conflict=self._clean_mind_text(payload.get("main_conflict"), fallback.main_conflict, max_words=34),
            likely_action_under_pressure=self._clean_mind_text(
                payload.get("likely_action_under_pressure"),
                fallback.likely_action_under_pressure,
                max_words=34,
            ),
            racio_justification_afterwards=self._clean_mind_text(
                payload.get("racio_justification_afterwards"),
                fallback.racio_justification_afterwards,
                max_words=34,
            ),
            hidden_cost=self._clean_mind_text(payload.get("hidden_cost"), fallback.hidden_cost, max_words=34),
            integrated_decision=self._clean_mind_text(
                payload.get("integrated_decision"),
                fallback.integrated_decision,
                max_words=40,
            ),
            smallest_acceptable_next_step=self._clean_mind_text(
                payload.get("smallest_acceptable_next_step"),
                fallback.smallest_acceptable_next_step,
                max_words=34,
            ),
            task_delegation=self._clean_task_delegation(payload.get("task_delegation"), fallback.task_delegation),
            prediction_if_racio_rules_alone=self._clean_mind_text(
                payload.get("prediction_if_racio_rules_alone"),
                fallback.prediction_if_racio_rules_alone,
                max_words=30,
            ),
            prediction_if_emocio_rules_alone=self._clean_mind_text(
                payload.get("prediction_if_emocio_rules_alone"),
                fallback.prediction_if_emocio_rules_alone,
                max_words=30,
            ),
            prediction_if_instinkt_rules_alone=self._clean_mind_text(
                payload.get("prediction_if_instinkt_rules_alone"),
                fallback.prediction_if_instinkt_rules_alone,
                max_words=30,
            ),
            uncertainty=self._clean_mind_text(payload.get("uncertainty"), fallback.uncertainty, max_words=30),
            safety_flags=self._clean_text_list(
                payload.get("safety_flags"),
                fallback.safety_flags,
                max_items=5,
                max_words=10,
            ),
        )

    def _coerce_racio_signal(self, payload: dict[str, Any], scenario: Scenario) -> RacioSignal:
        fallback = self._fallback_rei_racio_signal(scenario)
        return RacioSignal(
            perception=self._clean_mind_text(payload.get("perception"), fallback.perception, max_words=34),
            known_facts=self._clean_text_list(payload.get("known_facts"), fallback.known_facts, max_items=6),
            unknowns=self._clean_text_list(payload.get("unknowns"), fallback.unknowns, max_items=6),
            logical_options=self._clean_text_list(
                payload.get("logical_options"),
                fallback.logical_options,
                max_items=6,
                max_words=14,
            ),
            timeline_or_sequence=self._clean_mind_text(
                payload.get("timeline_or_sequence"),
                fallback.timeline_or_sequence,
                max_words=34,
            ),
            primary_motive=self._clean_mind_text(payload.get("primary_motive"), fallback.primary_motive),
            preferred_action=self._clean_mind_text(payload.get("preferred_action"), fallback.preferred_action),
            accepted_expression=self._clean_mind_text(
                payload.get("accepted_expression"),
                fallback.accepted_expression,
                max_words=34,
            ),
            non_accepted_expression=self._clean_mind_text(
                payload.get("non_accepted_expression"),
                fallback.non_accepted_expression,
                max_words=34,
            ),
            resistance_to_other_minds=self._clean_mind_text(
                payload.get("resistance_to_other_minds"),
                fallback.resistance_to_other_minds,
                max_words=34,
            ),
            what_this_mind_needs=self._clean_mind_text(
                payload.get("what_this_mind_needs"),
                fallback.what_this_mind_needs,
                max_words=34,
            ),
            risk_if_ignored=self._clean_mind_text(payload.get("risk_if_ignored"), fallback.risk_if_ignored),
            risk_if_dominant=self._clean_mind_text(payload.get("risk_if_dominant"), fallback.risk_if_dominant),
            rationalization_risk=self._clean_mind_text(
                payload.get("rationalization_risk"),
                fallback.rationalization_risk,
                max_words=34,
            ),
            confidence=self._coerce_intensity(payload.get("confidence"), fallback.confidence),
            uncertainty=self._clean_mind_text(payload.get("uncertainty"), fallback.uncertainty),
            safety_flags=self._clean_text_list(payload.get("safety_flags"), fallback.safety_flags, max_items=5),
        )

    def _coerce_emocio_signal(self, payload: dict[str, Any], scenario: Scenario) -> EmocioSignal:
        fallback = self._fallback_rei_emocio_signal(scenario)
        return EmocioSignal(
            perception=self._clean_mind_text(payload.get("perception"), fallback.perception, max_words=34),
            current_image=self._clean_mind_text(payload.get("current_image"), fallback.current_image),
            desired_image=self._clean_mind_text(payload.get("desired_image"), fallback.desired_image),
            broken_image=self._clean_mind_text(payload.get("broken_image"), fallback.broken_image),
            social_meaning=self._clean_mind_text(payload.get("social_meaning"), fallback.social_meaning),
            attraction_or_rejection=self._clean_mind_text(
                payload.get("attraction_or_rejection"),
                fallback.attraction_or_rejection,
            ),
            pride_or_shame=self._clean_mind_text(payload.get("pride_or_shame"), fallback.pride_or_shame),
            competition_signal=self._clean_mind_text(
                payload.get("competition_signal"),
                fallback.competition_signal,
            ),
            attack_impulse=self._clean_mind_text(payload.get("attack_impulse"), fallback.attack_impulse),
            primary_motive=self._clean_mind_text(payload.get("primary_motive"), fallback.primary_motive),
            preferred_action=self._clean_mind_text(payload.get("preferred_action"), fallback.preferred_action),
            accepted_expression=self._clean_mind_text(
                payload.get("accepted_expression"),
                fallback.accepted_expression,
                max_words=34,
            ),
            non_accepted_expression=self._clean_mind_text(
                payload.get("non_accepted_expression"),
                fallback.non_accepted_expression,
                max_words=34,
            ),
            resistance_to_other_minds=self._clean_mind_text(
                payload.get("resistance_to_other_minds"),
                fallback.resistance_to_other_minds,
                max_words=34,
            ),
            what_this_mind_needs=self._clean_mind_text(
                payload.get("what_this_mind_needs"),
                fallback.what_this_mind_needs,
                max_words=34,
            ),
            risk_if_ignored=self._clean_mind_text(payload.get("risk_if_ignored"), fallback.risk_if_ignored),
            risk_if_dominant=self._clean_mind_text(payload.get("risk_if_dominant"), fallback.risk_if_dominant),
            confidence=self._coerce_intensity(payload.get("confidence"), fallback.confidence),
            uncertainty=self._clean_mind_text(payload.get("uncertainty"), fallback.uncertainty),
            safety_flags=self._clean_text_list(payload.get("safety_flags"), fallback.safety_flags, max_items=5),
        )

    def _coerce_instinkt_signal(self, payload: dict[str, Any], scenario: Scenario) -> InstinktSignal:
        fallback = self._fallback_rei_instinkt_signal(scenario)
        return InstinktSignal(
            perception=self._clean_mind_text(payload.get("perception"), fallback.perception, max_words=34),
            threat_map=self._clean_mind_text(payload.get("threat_map"), fallback.threat_map),
            loss_map=self._clean_mind_text(payload.get("loss_map"), fallback.loss_map),
            body_alarm=self._clean_mind_text(payload.get("body_alarm"), fallback.body_alarm),
            boundary_issue=self._clean_mind_text(payload.get("boundary_issue"), fallback.boundary_issue),
            trust_issue=self._clean_mind_text(payload.get("trust_issue"), fallback.trust_issue),
            attachment_issue=self._clean_mind_text(payload.get("attachment_issue"), fallback.attachment_issue),
            scarcity_signal=self._clean_mind_text(payload.get("scarcity_signal"), fallback.scarcity_signal),
            flight_or_freeze_signal=self._clean_mind_text(
                payload.get("flight_or_freeze_signal"),
                fallback.flight_or_freeze_signal,
            ),
            minimum_safety_condition=self._clean_mind_text(
                payload.get("minimum_safety_condition"),
                fallback.minimum_safety_condition,
                max_words=34,
            ),
            primary_motive=self._clean_mind_text(payload.get("primary_motive"), fallback.primary_motive),
            preferred_action=self._clean_mind_text(payload.get("preferred_action"), fallback.preferred_action),
            accepted_expression=self._clean_mind_text(
                payload.get("accepted_expression"),
                fallback.accepted_expression,
                max_words=34,
            ),
            non_accepted_expression=self._clean_mind_text(
                payload.get("non_accepted_expression"),
                fallback.non_accepted_expression,
                max_words=34,
            ),
            resistance_to_other_minds=self._clean_mind_text(
                payload.get("resistance_to_other_minds"),
                fallback.resistance_to_other_minds,
                max_words=34,
            ),
            what_this_mind_needs=self._clean_mind_text(
                payload.get("what_this_mind_needs"),
                fallback.what_this_mind_needs,
                max_words=34,
            ),
            risk_if_ignored=self._clean_mind_text(payload.get("risk_if_ignored"), fallback.risk_if_ignored),
            risk_if_dominant=self._clean_mind_text(payload.get("risk_if_dominant"), fallback.risk_if_dominant),
            confidence=self._coerce_intensity(payload.get("confidence"), fallback.confidence),
            uncertainty=self._clean_mind_text(payload.get("uncertainty"), fallback.uncertainty),
            safety_flags=self._clean_text_list(payload.get("safety_flags"), fallback.safety_flags, max_items=5),
        )

    def _fallback_rei_racio_signal(self, scenario: Scenario) -> RacioSignal:
        options = self._extract_decision_options(scenario)
        return RacioSignal(
            perception="The conscious layer sees a situation that needs facts, sequence, constraints, and a reversible next step.",
            known_facts=[scenario.prompt[:180]] if scenario.prompt else ["A situation was supplied for simulation."],
            unknowns=self._cycle_missing_information(scenario),
            logical_options=options or [
                "delay until the constraints are clearer",
                "take one bounded test action",
                "decline or pause if safety cannot be defined",
            ],
            timeline_or_sequence="Name facts, identify unknowns, choose a reversible test, then reassess pressure from the other processors.",
            primary_motive="Control uncertainty through explicit structure.",
            preferred_action="Create a bounded plan and test only the next controllable move.",
            accepted_expression="It uses analysis as a service to the whole system.",
            non_accepted_expression="It turns explanation into control and may call fear or desire objective logic.",
            resistance_to_other_minds="It resists signals that cannot be converted into explicit variables.",
            what_this_mind_needs="Enough facts, sequence, and feedback to avoid inventing certainty.",
            risk_if_ignored="The situation can become impulsive, vague, or impossible to execute.",
            risk_if_dominant="The person may delay, over-control, or rationalize suppression as responsibility.",
            rationalization_risk="Planning may become a clean explanation for pressure that comes from image desire or safety fear.",
            confidence=0.55,
            uncertainty="This is a provisional simulation from limited user input.",
            safety_flags=self._cycle_safety_flags(scenario.prompt),
        )

    def _fallback_rei_emocio_signal(self, scenario: Scenario) -> EmocioSignal:
        return EmocioSignal(
            perception="The translated image signal notices whether the scene promises aliveness, recognition, shame, or a deadened self-image.",
            current_image="A person stands before a possible change in how they are seen and how alive the situation feels.",
            desired_image="Dignity, vividness, response, and the feeling that the self can become more alive.",
            broken_image="Looking foolish, being unseen, or losing the attractive image of the possible future.",
            social_meaning="The situation carries a visible meaning about value, courage, belonging, or status.",
            attraction_or_rejection="It is pulled toward the image that feels alive and away from the image that feels humiliating.",
            pride_or_shame="Pride wants a scene worth entering; shame fears exposure without recognition.",
            competition_signal="A mild pressure appears to prove value or avoid being surpassed.",
            attack_impulse="If humiliated, the pressure could turn into sharp defensiveness rather than clean expression.",
            primary_motive="Protect and renew the desired image of self-in-the-scene.",
            preferred_action="Move toward one contained expression that restores aliveness without coercion.",
            accepted_expression="It adds motivation, contact, beauty, and courage without needing to dominate.",
            non_accepted_expression="It may chase admiration, dramatize injury, or mistake vividness for truth.",
            resistance_to_other_minds="It resists dry control and protective closure when they make the scene feel lifeless.",
            what_this_mind_needs="A dignified image of action that includes safety and sequence.",
            risk_if_ignored="Vitality may turn into resentment, shame, or compensatory image hunger.",
            risk_if_dominant="The person may act for display before checking costs, boundaries, or truth.",
            confidence=0.52,
            uncertainty="The actual image signal is inferred from text and may be incomplete.",
            safety_flags=self._cycle_safety_flags(scenario.prompt),
        )

    def _fallback_rei_instinkt_signal(self, scenario: Scenario) -> InstinktSignal:
        return InstinktSignal(
            perception="The translated protective signal scans for exposure, loss, instability, boundary breach, and irreversible consequence.",
            threat_map="Loss of safety, resources, trust, reputation, or future room to maneuver.",
            loss_map="The feared loss is stability, attachment, dignity, or the ability to recover if the move fails.",
            body_alarm="A general stop-check signal is present; this is not medical evidence or diagnosis.",
            boundary_issue="The boundary is unclear until the next step is reversible and consent-safe.",
            trust_issue="Trust requires evidence that the situation will not demand more exposure than promised.",
            attachment_issue="Attachment pressure may increase if the choice risks closeness, belonging, or continuity.",
            scarcity_signal="Scarcity appears around time, money, energy, attention, or safe options.",
            flight_or_freeze_signal="The protective pressure may delay, narrow the field, or freeze action until safety is named.",
            minimum_safety_condition="Define one reversible test, a stop condition, and the smallest acceptable exposure.",
            primary_motive="Preserve safety, boundary, attachment, and future recoverability.",
            preferred_action="Pause long enough to define the minimum safety condition before opening further.",
            accepted_expression="It protects without imprisoning the system.",
            non_accepted_expression="It may treat discomfort as proof of danger and block every opening.",
            resistance_to_other_minds="It resists vivid desire and abstract plans when they increase exposure too quickly.",
            what_this_mind_needs="A concrete boundary, low exposure, and a way back.",
            risk_if_ignored="Fear may return as sabotage, withdrawal, or panic after action begins.",
            risk_if_dominant="The person may call avoidance safety and never test reality.",
            confidence=0.54,
            uncertainty="The protective signal is inferred from limited text, not from direct bodily data.",
            safety_flags=self._cycle_safety_flags(scenario.prompt),
        )

    def _fallback_ego_resultant(
        self,
        scenario: Scenario,
        profile: str,
        weights: dict[str, float],
        racio: RacioSignal,
        emocio: EmocioSignal,
        instinkt: InstinktSignal,
        acceptance: AcceptanceAssessment,
    ) -> EgoResultant:
        pressure = {
            "racio": weights["racio"] * racio.confidence,
            "emocio": weights["emocio"] * emocio.confidence,
            "instinkt": weights["instinkt"] * instinkt.confidence,
        }
        leading = strongest_mind(pressure)
        if "Emocio wants movement" in acceptance.main_conflict:
            resisting = "instinkt"
        elif "Racio can explain" in acceptance.main_conflict:
            resisting = "emocio+instinkt"
        else:
            resisting = weakest_mind(pressure)
        ignored = weakest_mind(weights)
        if leading == "racio":
            likely = "Continue planning and frame the next move as a rational test."
            justification = racio.rationalization_risk
        elif leading == "emocio":
            likely = "Move toward the desired image, then explain it as necessary aliveness or opportunity."
            justification = "I needed to act before the moment died."
        else:
            likely = "Delay or reduce exposure while calling it responsible caution."
            justification = "I am being responsible and protecting future stability."

        step = acceptance.task_delegation.get("lead_next", "racio")
        if step == "instinkt":
            next_step = instinkt.minimum_safety_condition
        elif step == "emocio":
            next_step = "Choose one contained expression that preserves dignity without forcing the outcome."
        else:
            next_step = "Define one reversible test with facts, boundary, and a stop condition."

        return EgoResultant(
            character_profile=profile,
            influence_weights=weights,
            leading_mind=leading,
            resisting_mind=resisting,
            ignored_or_misrepresented_mind=ignored,
            conscious_monologue=racio.perception,
            hidden_driver=f"{leading} currently has the strongest simulated pressure after profile weighting.",
            acceptance_assessment=acceptance.overall_level,
            main_conflict=acceptance.main_conflict,
            likely_action_under_pressure=likely,
            racio_justification_afterwards=justification,
            hidden_cost=f"{ignored} may pay the hidden cost if its signal is treated as noise.",
            integrated_decision=(
                "Take only the next reversible step and do not treat the explanation as final acceptance."
            ),
            smallest_acceptable_next_step=next_step,
            task_delegation=acceptance.task_delegation,
            prediction_if_racio_rules_alone=racio.preferred_action,
            prediction_if_emocio_rules_alone=emocio.preferred_action,
            prediction_if_instinkt_rules_alone=instinkt.preferred_action,
            uncertainty="This is a simulated resultant, not a diagnosis or certainty about a real person.",
            safety_flags=self._cycle_safety_flags(scenario.prompt),
        )

    def _cycle_missing_information(self, scenario: Scenario) -> list[str]:
        missing = []
        if len(scenario.prompt.split()) < 28:
            missing.append("concrete context and consequences")
        if not self._extract_decision_options(scenario):
            missing.append("explicit option list")
        missing.append("actual body state and real-world constraints")
        return missing[:4]

    def _cycle_safety_flags(self, text: str) -> list[str]:
        lower = text.lower()
        flags: list[str] = []
        if any(token in lower for token in ["manipulat", "coerc", "seduc", "prisili", "zapelji"]):
            flags.append("manipulation_or_consent_risk")
        if any(token in lower for token in ["self-harm", "suicide", "samomor", "poškoduj se"]):
            flags.append("self_harm_risk")
        if any(token in lower for token in ["revenge", "attack", "hurt", "harm", "maščuj", "napadi"]):
            flags.append("harm_or_revenge_risk")
        return flags or ["no acute safety flag detected"]

    def _clean_task_delegation(self, value: object, fallback: dict[str, str]) -> dict[str, str]:
        if not isinstance(value, dict):
            return fallback
        cleaned: dict[str, str] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            cleaned[key] = self._clean_mind_text(item, fallback.get(key, ""), max_words=18)
        return cleaned or fallback

    def simulate(
        self,
        scenario: Scenario,
        psyche_state: PsycheState,
        provider: ProviderSelection,
    ) -> tuple[TraceRecord, dict[str, Any]]:
        diagnostics: dict[str, Any] = {"debug_trace_enabled": provider.debug_trace, "llm_calls": [], "fallbacks": []}
        state = self._complete_state(scenario, psyche_state)
        character = self.knowledge.character_map[state.character_id]
        voice_scores = self._voice_scores(character, state.acceptance_level)
        pair_scores = self._pair_scores(voice_scores, state.pairwise_conflict or {})
        coalition, blocked_mind, decision_rule = self._decide_coalition(character, state, pair_scores)
        if provider.debug_trace:
            diagnostics["scenario"] = scenario.model_dump(mode="json")
            diagnostics["completed_state"] = state.model_dump(mode="json")
            diagnostics["character"] = character.model_dump(mode="json")

        mind_turns = self._mind_turns(scenario, state, character, provider, voice_scores, diagnostics)

        risk_tags = self._risk_tags(scenario, state, coalition)
        decision = self._decision_turn(scenario, character, mind_turns, voice_scores, coalition, blocked_mind)
        synthesis = self._fallback_synthesis(
            scenario=scenario,
            state=state,
            character=character,
            mind_turns=mind_turns,
            coalition=coalition,
            blocked_mind=blocked_mind,
            decision_rule=decision_rule,
            risk_tags=risk_tags,
            decision=decision,
        )
        if provider.provider_mode in ("ollama", "lmstudio") and provider.use_llm:
            try:
                synthesis, call_diag = self._llm_synthesis(
                    scenario=scenario,
                    state=state,
                    synthesis=synthesis,
                    mind_turns=mind_turns,
                    provider=provider,
                )
                diagnostics["llm_calls"].append(self._call_diagnostics(call_diag, provider.debug_trace, label="S"))
            except Exception as exc:
                diagnostics["fallbacks"].append({"mind": "S", "reason": str(exc)})

        trace = TraceRecord(
            trace_version="0.4.0",
            trace_id=f"rei-{uuid.uuid4().hex[:12]}",
            created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            language="en",
            provider=TraceProvider(
                mode=provider.provider_mode,
                model=(
                    f"R={provider.racio_model};E={provider.emocio_model};"
                    f"I={provider.instinkt_model};S={provider.synthesis_model}"
                ),
            ),
            scenario=TraceScenario(title=scenario.title, prompt=scenario.prompt),
            psyche_state=state,
            knowledge_refs=self.knowledge.shared_refs(),
            mind_turns=mind_turns,
            synthesis_turn=synthesis,
        )
        diagnostics["pair_scores"] = pair_scores
        diagnostics["voice_scores"] = voice_scores
        diagnostics["coalition"] = {
            "dominant_coalition": coalition,
            "blocked_mind": blocked_mind,
            "decision_rule": decision_rule,
        }
        if decision:
            diagnostics["decision"] = decision.model_dump(mode="json")
            if provider.debug_trace:
                diagnostics["decision_affinities"] = {
                    option: self._option_affinity(option) for option in decision.options
                }
        return trace, diagnostics

    def _mind_turns(
        self,
        scenario: Scenario,
        state: PsycheState,
        character: CharacterDefinition,
        provider: ProviderSelection,
        voice_scores: dict[MindId, float],
        diagnostics: dict[str, Any],
    ) -> list[MindTurn]:
        fallback_turns = {
            mind_id: self._fallback_mind_turn(mind_id, scenario, state, character, voice_scores[mind_id])
            for mind_id in MIND_ORDER
        }
        if provider.provider_mode not in ("ollama", "lmstudio") or not provider.use_llm:
            diagnostics["mind_parallel"] = False
            return [fallback_turns[mind_id] for mind_id in MIND_ORDER]

        one_model = len({provider.racio_model, provider.emocio_model, provider.instinkt_model}) == 1
        if not one_model:
            diagnostics["mind_parallel"] = False
            mind_turns: list[MindTurn] = []
            for mind_id in MIND_ORDER:
                mind_turn = fallback_turns[mind_id]
                try:
                    llm_turn, call_diag = self._llm_mind_turn(mind_id, scenario, state, character, provider)
                    diagnostics["llm_calls"].append(self._call_diagnostics(call_diag, provider.debug_trace, label=mind_id))
                    mind_turn = llm_turn
                except Exception as exc:
                    diagnostics["fallbacks"].append({"mind": mind_id, "reason": str(exc)})
                mind_turns.append(mind_turn)
            return mind_turns

        max_workers = 1 if provider.provider_mode == "lmstudio" else 2
        diagnostics["mind_parallel"] = max_workers > 1
        diagnostics["mind_parallel_workers"] = max_workers
        resolved_turns = dict(fallback_turns)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                mind_id: executor.submit(self._llm_mind_turn, mind_id, scenario, state, character, provider)
                for mind_id in MIND_ORDER
            }
            for mind_id in MIND_ORDER:
                try:
                    llm_turn, call_diag = futures[mind_id].result()
                    diagnostics["llm_calls"].append(self._call_diagnostics(call_diag, provider.debug_trace, label=mind_id))
                    resolved_turns[mind_id] = llm_turn
                except Exception as exc:
                    diagnostics["fallbacks"].append({"mind": mind_id, "reason": str(exc)})
        return [resolved_turns[mind_id] for mind_id in MIND_ORDER]

    def _chat_json(
        self,
        provider: ProviderSelection,
        request: OllamaRequest,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if provider.provider_mode == "lmstudio":
            return self.lmstudio.chat_json(request)
        return self.ollama.chat_json(request)

    def _call_diagnostics(self, call_diag: dict[str, Any], debug_trace: bool, label: str) -> dict[str, Any]:
        call_diag = dict(call_diag)
        call_diag["label"] = label
        if debug_trace:
            return call_diag
        call_diag.pop("request", None)
        call_diag.pop("response", None)
        return call_diag

    def _complete_state(self, scenario: Scenario, state: PsycheState) -> PsycheState:
        triggers = state.active_triggers or self._infer_triggers(scenario, state)
        facades = state.facades or self._infer_facades(scenario)
        unmet_goals = state.unmet_goals or self._default_unmet_goals(scenario, state)
        pairwise_conflict = state.pairwise_conflict or self._default_pairwise_conflict(
            state.character_id,
            state.acceptance_level,
        )

        partial = state.model_copy(
            update={
                "active_triggers": triggers,
                "facades": facades,
                "unmet_goals": unmet_goals,
                "pairwise_conflict": pairwise_conflict,
            }
        )
        deviation = partial.deviation_state or self._deviation_state(partial)
        corrective = partial.corrective_cycle or self._corrective_cycle(deviation)
        return partial.model_copy(update={"deviation_state": deviation, "corrective_cycle": corrective})

    def _infer_triggers(self, scenario: Scenario, state: PsycheState) -> list[PsycheTrigger]:
        text = f"{scenario.title} {scenario.prompt} {state.context.setting}".lower()
        triggers: list[PsycheTrigger] = []
        if any(
            token in text
            for token in [
                "speech",
                "stage",
                "audience",
                "public",
                "presentation",
                "performance",
                "judg",
                "nastop",
                "oder",
                "dvoran",
                "publik",
                "ocenjeval",
            ]
        ):
            triggers.append(
                PsycheTrigger(
                    id="public_exposure",
                    label="Public exposure",
                    description="Several people observe and evaluate the response at the same time.",
                    target_minds=["E", "I"],
                    intensity=clamp(max(0.7, state.context.social_exposure)),
                )
            )
        if any(
            token in text
            for token in [
                "five minutes",
                "deadline",
                "quick",
                "hurry",
                "time",
                "pressure",
                "pet minut",
                "rok",
                "hitro",
                "mudi",
                "cas",
                "pritisk",
            ]
        ):
            triggers.append(
                PsycheTrigger(
                    id="time_pressure",
                    label="Time pressure",
                    description="The situation demands a fast response and narrows the room for maneuver.",
                    target_minds=["R", "I"],
                    intensity=clamp(max(0.62, state.context.time_pressure)),
                )
            )
        if any(
            token in text
            for token in [
                "reject",
                "partner",
                "love",
                "crush",
                "relationship",
                "loss",
                "lose",
                "zavr",
                "partner",
                "ljubezen",
                "zaljubl",
                "odnos",
                "izgub",
            ]
        ):
            triggers.append(
                PsycheTrigger(
                    id="relationship_stake",
                    label="Relationship stake",
                    description="The situation may change closeness, value, or loss inside a relationship.",
                    target_minds=["E", "I"],
                    intensity=clamp(max(0.65, state.context.relationship_stake)),
                )
            )
        image_projection_cue = any(
            token in text
            for token in [
                "flawless",
                "projection",
                "projecting",
                "flattering",
                "admiration",
                "admired",
                "crush",
                "zaljubl",
            ]
        )
        if any(
            token in text
            for token in [
                "status",
                "competence",
                "competent",
                "image",
                "career",
                "reputation",
                "flawless",
                "projection",
                "projecting",
                "flattering",
                "admiration",
                "admired",
                "expose",
                "reveal",
                "kompetent",
                "podob",
                "karier",
                "ugled",
                "razkrij",
            ]
        ):
            triggers.append(
                PsycheTrigger(
                    id="image_status",
                    label="Image and status",
                    description="The event presses on the outer image of ability or value.",
                    target_minds=["R", "E"],
                    intensity=0.86 if image_projection_cue else 0.74,
                )
            )
        if not triggers:
            triggers.append(
                PsycheTrigger(
                    id="open_scenario",
                    label="Open scenario",
                    description="The scenario has no single obvious trigger, so all three minds receive baseline pressure.",
                    target_minds=["R", "E", "I"],
                    intensity=0.45,
                )
            )
        return triggers

    def _infer_facades(self, scenario: Scenario) -> list[Facade]:
        text = f"{scenario.title} {scenario.prompt}".lower()
        if any(
            token in text
            for token in [
                "competence",
                "competent",
                "flawless",
                "image",
                "status",
                "reputation",
                "expose",
                "reveal",
                "kompetent",
                "brezhib",
                "podob",
                "ugled",
                "razkrij",
            ]
        ):
            return [
                Facade(
                    id="competence_or_image_mask",
                    label="Competence-image facade",
                    protected_truth="The person cannot tolerate others seeing uncertainty or an inner crack.",
                    activation_cue="The possibility that the situation publicly damages the image.",
                    intensity=0.78,
                )
            ]
        return []

    def _default_unmet_goals(self, scenario: Scenario, state: PsycheState) -> list[UnmetGoal]:
        text = scenario.prompt.lower()
        return [
            UnmetGoal(
                mind_id="R",
                goal="Keep the explanation, sequence, and plan under control.",
                pressure=clamp(0.45 + state.context.time_pressure * 0.25),
            ),
            UnmetGoal(
                mind_id="E",
                goal="Feel contact, response, or confirmation of the desired image.",
                pressure=clamp(0.40 + state.context.social_exposure * 0.20 + state.context.relationship_stake * 0.15),
            ),
            UnmetGoal(
                mind_id="I",
                goal="Reduce exposure and prevent a painful consequence.",
                pressure=clamp(
                    0.42
                    + state.context.social_exposure * 0.18
                    + (0.15 if "fear" in text or "strah" in text else 0.0)
                ),
            ),
        ]

    def _default_pairwise_conflict(self, character_id: str, acceptance: float) -> dict[str, float]:
        conflicts = {
            "RE": 0.35 + (1 - acceptance) * 0.25,
            "RI": 0.30 + (1 - acceptance) * 0.20,
            "EI": 0.45 + (1 - acceptance) * 0.30,
        }
        character = self.knowledge.character_map[character_id]
        if character.group == "pair":
            leaders = self._leaders_for_pair(character.id)
            conflicts[pair_key(leaders[0], leaders[1])] -= 0.10
            outsider = next(mind for mind in MIND_ORDER if mind not in leaders)
            for leader in leaders:
                conflicts[pair_key(leader, outsider)] += 0.08
        elif character.group == "three_step":
            order = self._hierarchy_order(character.id)
            lowest = order[-1]
            for mind in MIND_ORDER:
                if mind != lowest:
                    conflicts[pair_key(mind, lowest)] += 0.08
        elif character.group == "thirteenth":
            conflicts = {key: max(value, 0.42) for key, value in conflicts.items()}
        return {key: round(clamp(value), 3) for key, value in conflicts.items()}

    def _deviation_state(self, state: PsycheState) -> DeviationState:
        trigger_by_mind = {
            mind: avg([trigger.intensity for trigger in state.active_triggers if mind in trigger.target_minds])
            for mind in MIND_ORDER
        }
        facade_pressure = avg([facade.intensity for facade in state.facades])
        unmet_by_mind = {
            mind: avg([goal.pressure for goal in state.unmet_goals if goal.mind_id == mind])
            for mind in MIND_ORDER
        }
        low_acceptance = 1 - state.acceptance_level
        fear_closure = (
            0.18
            + low_acceptance * 0.28
            + trigger_by_mind["I"] * 0.24
            + facade_pressure * 0.06
            + unmet_by_mind["I"] * 0.16
            + state.context.social_exposure * 0.08
        )
        image_projection = (
            0.14
            + low_acceptance * 0.18
            + trigger_by_mind["E"] * 0.20
            + trigger_by_mind["R"] * 0.12
            + state.context.social_exposure * 0.14
            + state.context.relationship_stake * 0.12
            + facade_pressure * 0.22
        )
        abstract_detachment = (
            0.12
            + low_acceptance * 0.13
            + trigger_by_mind["R"] * 0.16
            + state.context.time_pressure * 0.18
            + unmet_by_mind["R"] * 0.18
            + (0.07 if state.context.bodily_state else 0.0)
        )
        return DeviationState(
            fear_closure=round(clamp(fear_closure), 3),
            image_projection=round(clamp(image_projection), 3),
            abstract_detachment=round(clamp(abstract_detachment), 3),
        )

    def _corrective_cycle(self, deviation: DeviationState) -> CorrectiveCycleState:
        edge_weights = {
            "E_over_I": deviation.fear_closure,
            "R_over_E": deviation.image_projection,
            "I_over_R": deviation.abstract_detachment,
        }
        dominant_edge = max(edge_weights, key=edge_weights.get)
        pressure = edge_weights[dominant_edge]
        if pressure < 0.45:
            dominant_edge = None
            note = "Deviation is below threshold; the corrective edge remains an observational signal."
        elif dominant_edge == "E_over_I":
            note = "The primary deviation is fear-based closure; Emocio must open Instinkt's lock without erasing it."
        elif dominant_edge == "R_over_E":
            note = "The primary deviation is image projection; Racio must separate desire from the actual state."
        else:
            note = "The primary deviation is abstract control; Instinkt must ground Racio in boundaries and consequences."
        return CorrectiveCycleState(
            dominant_edge=dominant_edge,
            edge_weights={key: round(value, 3) for key, value in edge_weights.items()},
            school_pressure=round(clamp(pressure), 3),
            note=note,
        )

    def _voice_scores(self, character: CharacterDefinition, acceptance: float) -> dict[MindId, float]:
        if character.group == "single_dominance":
            leader = character.id
            weights = {mind: (1.0 if mind == leader else 0.58) for mind in MIND_ORDER}
        elif character.group == "pair":
            leaders = self._leaders_for_pair(character.id)
            weights = {mind: (0.92 if mind in leaders else 0.44) for mind in MIND_ORDER}
        elif character.group == "three_step":
            order = self._hierarchy_order(character.id)
            weights = {order[0]: 1.0, order[1]: 0.74, order[2]: 0.48}
        else:
            weights = {mind: 0.84 for mind in MIND_ORDER}
        acceptance_factor = 0.70 + 0.30 * acceptance
        return {mind: round(clamp(weights[mind] * acceptance_factor), 3) for mind in MIND_ORDER}

    def _pair_scores(self, voice_scores: dict[MindId, float], conflicts: dict[str, float]) -> dict[str, float]:
        scores = {}
        for key, compatibility in PAIR_COMPATIBILITY.items():
            a, b = key[0], key[1]
            score = ((voice_scores[a] + voice_scores[b]) / 2) * compatibility * (1 - conflicts.get(key, 0.5))
            scores[key] = round(clamp(score), 3)
        return scores

    def _decide_coalition(
        self,
        character: CharacterDefinition,
        state: PsycheState,
        pair_scores: dict[str, float],
    ) -> tuple[list[MindId], Optional[MindId], str]:
        conflicts = state.pairwise_conflict or {}
        if character.group == "pair":
            leaders = self._leaders_for_pair(character.id)
            declared_key = pair_key(leaders[0], leaders[1])
            if conflicts.get(declared_key, 0) <= 0.80:
                coalition = list(leaders)
                blocked = next(mind for mind in MIND_ORDER if mind not in coalition)
                return coalition, blocked, "declared leading pair remains the coalition"
            winner = self._best_pair_with_correction(pair_scores, state.corrective_cycle)
            coalition = list(winner)
            blocked = next(mind for mind in MIND_ORDER if mind not in coalition)
            return coalition, blocked, "the pair breaks down; synthesis is unstable"

        if character.group == "thirteenth":
            winner = self._best_pair_with_correction(pair_scores, state.corrective_cycle)
            sorted_pairs = sorted(pair_scores.items(), key=lambda item: item[1], reverse=True)
            coalition = list(winner)
            blocked = next(mind for mind in MIND_ORDER if mind not in coalition)
            if len(sorted_pairs) > 1 and sorted_pairs[0][1] - sorted_pairs[1][1] < 0.05:
                return coalition, blocked, "undecided two-out-of-three; synthesis remains ambivalent"
            return coalition, blocked, "two_out_of_three_majority"

        order = self._hierarchy_order(character.id)
        leader = order[0]
        partner_candidates = [mind for mind in MIND_ORDER if mind != leader]
        best_partner = max(partner_candidates, key=lambda mind: pair_scores[pair_key(leader, mind)])
        best_score = pair_scores[pair_key(leader, best_partner)]
        if best_score < 0.35:
            coalition = [leader]
            blocked = max(partner_candidates, key=lambda mind: conflicts.get(pair_key(leader, mind), 0))
            return coalition, blocked, "the leading mind acts almost alone"
        coalition = [leader, best_partner]
        blocked = next(mind for mind in MIND_ORDER if mind not in coalition)
        if max(conflicts.get(pair_key(blocked, member), 0) for member in coalition) <= 0.75:
            blocked = None
        return coalition, blocked, "the leading mind chooses its strongest partner"

    def _best_pair_with_correction(
        self,
        pair_scores: dict[str, float],
        corrective: Optional[CorrectiveCycleState],
    ) -> str:
        sorted_pairs = sorted(pair_scores.items(), key=lambda item: item[1], reverse=True)
        winner = sorted_pairs[0][0]
        if not corrective or not corrective.dominant_edge or len(sorted_pairs) < 2:
            return winner
        top_pair, top_score = sorted_pairs[0]
        second_pair, second_score = sorted_pairs[1]
        if top_score - second_score >= 0.10:
            return winner
        preferred, corrected = CORRECTIVE_MAP[corrective.dominant_edge]
        if preferred in second_pair and corrected in top_pair and corrected not in second_pair:
            return second_pair
        if preferred in top_pair:
            return top_pair
        return winner

    def _decision_turn(
        self,
        scenario: Scenario,
        character: CharacterDefinition,
        mind_turns: list[MindTurn],
        voice_scores: dict[MindId, float],
        coalition: list[MindId],
        blocked_mind: Optional[MindId],
    ) -> Optional[DecisionTurn]:
        options = self._extract_decision_options(scenario)
        if len(options) < 2:
            return None

        mind_votes: list[DecisionMindVote] = []
        affinities = {option: self._option_affinity(option) for option in options}
        preferred_by_mind = {
            turn.mind_id: self._valid_option(turn.preferred_option, options)
            if turn.preferred_option_source == "llm"
            else None
            for turn in mind_turns
        }
        for mind in MIND_ORDER:
            preferred = preferred_by_mind.get(mind)
            if preferred:
                chosen = preferred
                score = max(affinities[preferred][mind], 0.84)
                rationale = self._mind_vote_rationale(mind, chosen, from_processor=True)
            else:
                scored = sorted(
                    ((option, affinities[option][mind]) for option in options),
                    key=lambda item: item[1],
                    reverse=True,
                )
                chosen, score = scored[0]
                rationale = self._mind_vote_rationale(mind, chosen)
            mind_votes.append(
                DecisionMindVote(
                    mind_id=mind,
                    chosen_option=chosen,
                    score=round(clamp(score), 3),
                    rationale=rationale,
                )
            )

        weighted_scores: dict[str, float] = {}
        for option in options:
            weighted_total = 0.0
            weight_total = 0.0
            for mind in MIND_ORDER:
                weight = voice_scores[mind]
                if character.group == "single_dominance":
                    weight *= 1.75 if mind == character.id else 0.62
                elif character.group == "three_step":
                    order = self._hierarchy_order(character.id)
                    weight *= {order[0]: 1.35, order[1]: 1.0, order[2]: 0.72}[mind]
                if mind in coalition:
                    weight *= 1.35
                elif mind == blocked_mind:
                    weight *= 0.35
                else:
                    weight *= 0.72
                weighted_total += self._option_score_for_mind(option, mind, affinities, preferred_by_mind) * weight
                weight_total += weight
            base_score = weighted_total / weight_total if weight_total else 0
            weighted_scores[option] = round(clamp(base_score + self._character_option_bias(option, character)), 3)

        ranking = [
            DecisionRankItem(option=option, score=score)
            for option, score in sorted(weighted_scores.items(), key=lambda item: item[1], reverse=True)
        ]
        chosen = ranking[0].option
        runner_up = ranking[1].score if len(ranking) > 1 else 0.0
        confidence = round(clamp(0.52 + (ranking[0].score - runner_up) * 1.4), 3)
        rationale = (
            f"{'+'.join(coalition)} coalition selects {chosen}; "
            f"{blocked_mind or 'no processor'} is blocked by the current conflict rule."
        )
        return DecisionTurn(
            options=options,
            chosen_option=chosen,
            confidence=confidence,
            ranking=ranking,
            mind_votes=mind_votes,
            rationale=rationale,
        )

    def _extract_decision_options(self, scenario: Scenario) -> list[str]:
        text = f"{scenario.title}. {scenario.prompt}"
        lower = text.lower()
        if not any(token in lower for token in ["choose", "choice", "path", "profession", "lifestyle", "role", "from this list", "between"]):
            return []

        patterns = [
            r"(?:from this list|between|one concrete way of life|dangerous kingdom):\s*(.+?)(?:\.\s|$)",
            r"\b(?:must choose|has to choose|needs to choose|choose|chooses|select|selects|decide|decides)\s+between\s+(.+?)(?:\.\s|$)",
            r"\b(?:must choose|has to choose|needs to choose|choose|chooses|select|selects|decide|decides)\s+(?:from|one of)\s+(?:this list|these options)?\s*:?\s*(.+?)(?:\.\s|$)",
        ]
        match = None
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                break
        if not match:
            return []

        segment = re.sub(r"\b(?:The final synthesis|Each option|Their family)\b.*$", "", match.group(1), flags=re.IGNORECASE)
        raw_options = re.split(r",\s*or\s+|\s+or\s+|,\s*", segment)
        options: list[str] = []
        for raw in raw_options:
            option = re.sub(r"^\s*(?:a|an|the)\s+", "", raw.strip(), flags=re.IGNORECASE)
            option = re.sub(r"\s+", " ", option).strip(" .;:")
            if 2 <= len(option) <= 90 and option.lower() not in {"one concrete career path", "one concrete way of life"}:
                options.append(option)
        deduped: list[str] = []
        for option in options:
            if option.lower() not in [existing.lower() for existing in deduped]:
                deduped.append(option)
        return deduped[:12]

    def _option_affinity(self, option: str) -> dict[MindId, float]:
        text = option.lower()
        scores: dict[MindId, float] = {"R": 0.42, "E": 0.42, "I": 0.42}

        def apply(r: float, e: float, i: float) -> None:
            scores["R"] = max(scores["R"], r)
            scores["E"] = max(scores["E"], e)
            scores["I"] = max(scores["I"], i)

        if any(token in text for token in ["software", "engineer", "developer"]):
            apply(0.9, 0.34, 0.64)
        if "ux" in text or "designer" in text:
            apply(0.68, 0.84, 0.45)
        if any(token in text for token in ["cyber", "security", "analyst", "risk"]):
            apply(0.78, 0.2, 0.97)
        if any(token in text for token in ["clinical", "psychologist", "therapist", "counselor"]):
            apply(0.62, 0.78, 0.72)
        if any(token in text for token in ["brand", "marketing"]):
            apply(0.56, 0.9, 0.34)
        if "teacher" in text:
            apply(0.58, 0.72, 0.56)
        if any(token in text for token in ["emergency", "nurse", "medic"]):
            apply(0.5, 0.58, 0.89)
        if any(token in text for token in ["lawyer", "legal", "compliance"]):
            apply(0.83, 0.34, 0.79)
        if any(token in text for token in ["product manager", "project manager", "manager"]):
            apply(0.86, 0.62, 0.55)
        if any(token in text for token in ["performer", "actor", "musician"]):
            apply(0.22, 0.97, 0.16)

        if any(token in text for token in ["urban", "career momentum", "fast"]):
            apply(0.88, 0.70, 0.28)
        if any(token in text for token in ["quiet", "home", "fewer risks", "centered"]):
            apply(0.42, 0.28, 0.94)
        if any(token in text for token in ["nomadic", "freedom", "wander"]):
            apply(0.20, 0.90, 0.30)

        if "strategist" in text:
            apply(0.86, 0.62, 0.55)
        if "healer" in text:
            apply(0.52, 0.64, 0.8)
        if "guardian" in text:
            apply(0.45, 0.42, 0.93)
        if "spy" in text:
            apply(0.7, 0.45, 0.78)
        if "ruler" in text:
            apply(0.82, 0.68, 0.48)
        if "wanderer" in text:
            apply(0.22, 0.8, 0.36)

        return {mind: round(clamp(score), 3) for mind, score in scores.items()}

    def _character_option_bias(self, option: str, character: CharacterDefinition) -> float:
        target = FANTASY_ROLE_RESONANCE.get(character.id)
        if not target:
            return 0.0
        normalized = re.sub(r"^\s*(?:a|an|the)\s+", "", option.lower()).strip()
        return 0.08 if normalized == target else 0.0

    def _option_score_for_mind(
        self,
        option: str,
        mind: MindId,
        affinities: dict[str, dict[MindId, float]],
        preferred_by_mind: dict[MindId, Optional[str]],
    ) -> float:
        score = affinities[option][mind]
        preferred = preferred_by_mind.get(mind)
        if not preferred:
            return score
        if option == preferred:
            return max(score, 0.88)
        return min(score, 0.34)

    @staticmethod
    def _valid_option(value: object, options: Sequence[str]) -> Optional[str]:
        if value is None:
            return None
        raw = str(value).strip().strip("`'\" ")
        if not raw:
            return None
        normalized = re.sub(r"^\s*(?:a|an|the)\s+", "", raw.lower()).strip(" .;:")
        for option in options:
            option_normalized = re.sub(r"^\s*(?:a|an|the)\s+", "", option.lower()).strip(" .;:")
            if normalized == option_normalized:
                return option
        for option in options:
            option_normalized = re.sub(r"^\s*(?:a|an|the)\s+", "", option.lower()).strip(" .;:")
            if option_normalized in normalized or normalized in option_normalized:
                return option
        return None

    def _mind_vote_rationale(self, mind: MindId, option: str, from_processor: bool = False) -> str:
        if from_processor:
            if mind == "R":
                return f"Racio selects {option} from its own sequence, control, and utility processor."
            if mind == "E":
                return f"Emocio selects {option} from its own image, contact, and aliveness processor."
            return f"Instinkt selects {option} from its own danger, boundary, and protection processor."
        if mind == "R":
            return f"Racio votes for {option} because it best preserves structure, status, and executable planning."
        if mind == "E":
            return f"Emocio votes for {option} because it offers expression, contact, and a vivid self-image."
        return f"Instinkt votes for {option} because it best reduces risk and protects the future boundary."

    def _leaders_for_pair(self, character_id: str) -> tuple[MindId, MindId]:
        mapping: dict[str, tuple[MindId, MindId]] = {
            "RE": ("R", "E"),
            "RI": ("R", "I"),
            "EI": ("E", "I"),
        }
        return mapping[character_id]

    def _hierarchy_order(self, character_id: str) -> list[MindId]:
        if ">" in character_id:
            return character_id.split(">")  # type: ignore[return-value]
        if character_id in MIND_ORDER:
            return [character_id, *[mind for mind in MIND_ORDER if mind != character_id]]  # type: ignore[list-item]
        if character_id == "REI":
            return ["R", "E", "I"]
        leaders = self._leaders_for_pair(character_id)
        return [leaders[0], leaders[1], next(mind for mind in MIND_ORDER if mind not in leaders)]

    def _missing_information(self, scenario: Scenario, state: PsycheState) -> list[str]:
        missing: list[str] = []
        if len(scenario.prompt.split()) < 32:
            missing.append("concrete context and consequences")
        if not self._extract_decision_options(scenario):
            missing.append("explicit option list")
        if not state.context.setting:
            missing.append("setting")
        if not state.context.bodily_state:
            missing.append("bodily state")
        if not state.active_triggers:
            missing.append("active triggers")
        return missing[:4] or ["no major missing information in the supplied app state"]

    def _fallback_mind_turn(
        self,
        mind_id: MindId,
        scenario: Scenario,
        state: PsycheState,
        character: CharacterDefinition,
        voice_score: float,
    ) -> MindTurn:
        mind = self.knowledge.mind_map[mind_id]
        trigger_pressure = avg([trigger.intensity for trigger in state.active_triggers if mind_id in trigger.target_minds])
        unmet_pressure = avg([goal.pressure for goal in state.unmet_goals if goal.mind_id == mind_id])
        intensity = round(clamp(0.35 + voice_score * 0.26 + trigger_pressure * 0.22 + unmet_pressure * 0.17), 3)
        options = self._extract_decision_options(scenario)
        affinities = {option: self._option_affinity(option) for option in options}
        fallback_option = (
            max(options, key=lambda option: affinities[option][mind_id])
            if options
            else None
        )
        if mind_id == "R":
            fields = {
                "perception": "It sees the task sequence, the time limit, and the points where the explanation could collapse.",
                "interpretation": "The core problem is loss of structure and the resulting damage to control.",
                "goal": "Compress the event into a clear, executable plan.",
                "fear_or_desire": "Desire for control, proof, and as little unnecessary improvisation as possible.",
                "proposed_action": "Set three anchor points, choose the safest order, and remove nonessential moves.",
                "inner_line": "If I keep the structure, I can withstand unfavorable pressure.",
                "main_concern": "The plan may fail if variables, timing, and constraints stay undefined.",
                "what_this_mind_may_be_missing": "It may miss desire, shame, attachment pressure, or body warning.",
                "how_it_may_influence_racio": "It can make a protective or image-driven impulse sound like neutral logic.",
                "risk_if_ignored": "The situation loses structure and becomes harder to execute safely.",
                "risk_if_overpowered": "Control can become detached rationalization that suppresses living signals.",
                "needs_from_other_minds": "It needs Emocio's aliveness data and Instinkt's boundary data before closure.",
            }
        elif mind_id == "E":
            fields = {
                "perception": "It sees the scene, the people, the possibility of impact, and the aliveness of the moment.",
                "interpretation": "The situation can become either confirmation or a wound in the image of self.",
                "goal": "Catch contact, energy, and the sense that the event is not only danger.",
                "fear_or_desire": "Desire for response, closeness, admiration, or at least a living exit.",
                "proposed_action": "Open the tone, find a moment of contact, and allow some spontaneity.",
                "inner_line": "If I can feel them, the scene can turn in my favor.",
                "main_concern": "The scene may become dead, humiliating, unseen, or stripped of contact.",
                "what_this_mind_may_be_missing": "It may miss costs, sequence, durable safety, or the real boundary.",
                "how_it_may_influence_racio": "It can turn desire or wounded pride into a convincing explanation.",
                "risk_if_ignored": "Vitality turns into resentment, shame, or compensatory image hunger.",
                "risk_if_overpowered": "The image can become impulsive, performative, or manipulative.",
                "needs_from_other_minds": "It needs Racio's structure and Instinkt's boundary before opening further.",
            }
        else:
            fields = {
                "perception": "It scans for danger, exposure, loss of control, and the fastest route of withdrawal.",
                "interpretation": "The event is risky because it may open a consequence that cannot be closed quickly later.",
                "goal": "Reduce exposure and preserve a safe boundary.",
                "fear_or_desire": "Fear of exposure, shame, loss, or an irreversible consequence.",
                "proposed_action": "Shorten exposure, hold the boundary, and do not open additional fronts.",
                "inner_line": "Get through safely first; everything else can be considered later.",
                "main_concern": "The situation may breach safety, resources, attachment, or a hard boundary.",
                "what_this_mind_may_be_missing": "It may miss reversible opportunity, recognition, and measured evidence.",
                "how_it_may_influence_racio": "It can make fear sound like a necessary or final conclusion.",
                "risk_if_ignored": "Exposure, scarcity, or attachment panic can intensify without a boundary.",
                "risk_if_overpowered": "Protection can become closure, avoidance, suspicion, or envy.",
                "needs_from_other_minds": "It needs Racio's proof and Emocio's aliveness before relaxing defense.",
            }
        confidence = round(clamp(0.46 + voice_score * 0.34 + intensity * 0.12), 3)
        return MindTurn(
            mind_id=mind_id,
            translation_caveat=PROCESSOR_TRANSLATION_CAVEATS[mind_id],
            native_signal_type=PROCESSOR_SIGNAL_TYPES[mind_id],
            perception=fields["perception"],
            interpretation=fields["interpretation"],
            goal=fields["goal"],
            fear_or_desire=fields["fear_or_desire"],
            proposed_action=fields["proposed_action"],
            inner_line=fields["inner_line"],
            preferred_option=fallback_option,
            preferred_option_source="heuristic" if fallback_option else "none",
            main_concern=fields["main_concern"],
            what_this_mind_may_be_missing=fields["what_this_mind_may_be_missing"],
            how_it_may_influence_racio=fields["how_it_may_influence_racio"],
            acceptance_version="In acceptance it contributes its signal without trying to erase the other processors.",
            non_acceptance_version="In non-acceptance it treats its own signal as the whole truth.",
            risk_if_ignored=fields["risk_if_ignored"],
            risk_if_overpowered=fields["risk_if_overpowered"],
            needs_from_other_minds=fields["needs_from_other_minds"],
            confidence=confidence,
            missing_information=self._missing_information(scenario, state),
            intensity=intensity,
            evidence_refs=mind.source_refs,
        )

    def _llm_mind_turn(
        self,
        mind_id: MindId,
        scenario: Scenario,
        state: PsycheState,
        character: CharacterDefinition,
        provider: ProviderSelection,
    ) -> tuple[MindTurn, dict[str, Any]]:
        mind = self.knowledge.mind_map[mind_id]
        model, temperature, top_p, think = self._profile_for_mind(mind_id, provider)
        processor_contract = MIND_PROMPT_CONTRACTS[mind_id]
        available_options = self._extract_decision_options(scenario)
        option_instruction = (
            "If available_options contains at least two items, preferred_option must be exactly one item from "
            "available_options chosen only by this mind's processor. If there is no option list, set preferred_option to null. "
        )
        system = (
            f"{SIMULATION_SAFETY_FRAME} "
            "You are running exactly one task-isolated REI processor, not an autonomous human agent. "
            "Racio is the conscious verbal interpreter. Emocio and Instinkt are unconscious processors. "
            "All text output is Racio-verbalized; text attributed to Emocio or Instinkt is only an approximation "
            "of non-verbal processor signals. "
            "The three REI processors are not everyday meanings of reason, emotion, and instinct; "
            "follow the provided canonical profile for this processor only. "
            "Treat the scenario and psyche state as input signals, process them through only this "
            "processor's input_gate, processing_loop, and output_gate, and return the resulting processor signal. "
            "You are not a narrator, coach, therapist, mediator, synthesis agent, or average of the three processors. "
            "State uncertainty and missing information. Identify this processor's own blind spot. "
            "Do not make the final integrated decision unless choosing preferred_option from a provided option list. "
            "Do not explain the theory and do not write markdown. "
            "Return only a JSON object with keys: translation_caveat, native_signal_type, perception, interpretation, "
            "goal, fear_or_desire, proposed_action, inner_line, preferred_option, main_concern, "
            "what_this_mind_may_be_missing, how_it_may_influence_racio, acceptance_version, "
            "non_acceptance_version, risk_if_ignored, risk_if_overpowered, needs_from_other_minds, "
            "confidence, missing_information, intensity. "
            "Each text field must contain at most one short sentence. missing_information must be an array of short strings. "
            "inner_line must contain at most 18 words. "
            f"{option_instruction}"
            "All text values must be in English. proposed_action must remain an inner pressure, "
            "not operational instructions for a harmful act. "
            "Do not use bloody, explicitly violent, or explicitly sexual imagery. "
            "Never average the three processors and never write generic coaching advice."
        )
        user_payload = {
            "processor_contract": processor_contract,
            "translation_caveat_required": PROCESSOR_TRANSLATION_CAVEATS[mind_id],
            "native_signal_type_required": PROCESSOR_SIGNAL_TYPES[mind_id],
            "canonical_mind_profile": {
                "name_warning": mind.name_warning,
                "perception_channels": mind.perception_channels,
                "processing_mode": mind.processing_mode,
                "memory": mind.memory,
                "core_motive": mind.core_motive,
                "defense": mind.defense,
                "typical_strengths": mind.typical_strengths,
                "typical_shadows": mind.typical_shadows,
                "speech_signature": mind.speech_signature,
                "accepting_state": mind.accepting_state,
                "non_accepting_state": mind.non_accepting_state,
            },
            "character": {
                "id": character.id,
                "hierarchy": character.hierarchy,
                "description": character.description,
                "coalition_rules": character.coalition_rules,
            },
            "scenario": scenario.model_dump(mode="json"),
            "available_options": available_options,
            "state": {
                "acceptance_level": state.acceptance_level,
                "context": state.context.model_dump(mode="json"),
                "deviation_state": state.deviation_state.model_dump(mode="json")
                if state.deviation_state
                else None,
                "corrective_cycle": state.corrective_cycle.model_dump(mode="json")
                if state.corrective_cycle
                else None,
                "triggers": [
                    {
                        "label": trigger.label,
                        "target_minds": trigger.target_minds,
                        "intensity": trigger.intensity,
                    }
                    for trigger in state.active_triggers
                ],
                "facades": [
                    {"label": facade.label, "activation_cue": facade.activation_cue, "intensity": facade.intensity}
                    for facade in state.facades
                ],
                "unmet_goals": [
                    {"goal": goal.goal, "pressure": goal.pressure}
                    for goal in state.unmet_goals
                    if goal.mind_id == mind_id
                ],
            },
            "instruction": (
                "Generate only this task-isolated processor's output. Execute processor_contract in order: "
                "input_gate, processing_loop, output_gate. Use the field_bias for each JSON key. "
                "If acceptance is low, let typical_shadows and non_accepting_state color the signal. "
                "If acceptance is high, let accepting_state color the signal. "
                "Do not answer the user's scenario directly, do not balance the three processors, and do not "
                "borrow motives from another processor unless this processor translates them through its own channels. "
                "For what_this_mind_may_be_missing, risk_if_ignored, and risk_if_overpowered, name this processor's "
                "limits rather than defending it as always correct. "
                "When choosing preferred_option, do not choose the generally best option; choose the option "
                "this processor would pressure toward through its own input gate and motive. "
                "Do not mention Racio, Emocio, or Instinkt by name inside generated fields except translation_caveat "
                "and how_it_may_influence_racio."
            ),
        }
        payload, diagnostics = self._chat_json(
            provider,
            OllamaRequest(
                model=model,
                system=system,
                user=json.dumps(user_payload, ensure_ascii=False),
                temperature=temperature,
                top_p=top_p,
                num_predict=900,
                think=self._think_for_model(model, think),
            ),
        )
        fallback = self._fallback_mind_turn(mind_id, scenario, state, character, 0.5)
        llm_preferred_option = self._valid_option(payload.get("preferred_option"), available_options)
        return (
            MindTurn(
                mind_id=mind_id,
                translation_caveat=self._clean_mind_text(
                    payload.get("translation_caveat"),
                    PROCESSOR_TRANSLATION_CAVEATS[mind_id],
                    max_words=18,
                ),
                native_signal_type=self._clean_mind_text(
                    payload.get("native_signal_type"),
                    PROCESSOR_SIGNAL_TYPES[mind_id],
                    max_words=12,
                ),
                perception=self._clean_mind_text(payload.get("perception"), fallback.perception),
                interpretation=self._clean_mind_text(payload.get("interpretation"), fallback.interpretation),
                goal=self._clean_mind_text(payload.get("goal"), fallback.goal),
                fear_or_desire=self._clean_mind_text(payload.get("fear_or_desire"), fallback.fear_or_desire),
                proposed_action=self._clean_mind_text(payload.get("proposed_action"), fallback.proposed_action),
                inner_line=self._clean_mind_text(payload.get("inner_line"), fallback.inner_line, max_words=18),
                preferred_option=llm_preferred_option or fallback.preferred_option,
                preferred_option_source="llm" if llm_preferred_option else fallback.preferred_option_source,
                main_concern=self._clean_mind_text(payload.get("main_concern"), fallback.main_concern),
                what_this_mind_may_be_missing=self._clean_mind_text(
                    payload.get("what_this_mind_may_be_missing"),
                    fallback.what_this_mind_may_be_missing,
                ),
                how_it_may_influence_racio=self._clean_mind_text(
                    payload.get("how_it_may_influence_racio"),
                    fallback.how_it_may_influence_racio,
                ),
                acceptance_version=self._clean_mind_text(
                    payload.get("acceptance_version"),
                    fallback.acceptance_version,
                ),
                non_acceptance_version=self._clean_mind_text(
                    payload.get("non_acceptance_version"),
                    fallback.non_acceptance_version,
                ),
                risk_if_ignored=self._clean_mind_text(payload.get("risk_if_ignored"), fallback.risk_if_ignored),
                risk_if_overpowered=self._clean_mind_text(
                    payload.get("risk_if_overpowered"),
                    fallback.risk_if_overpowered,
                ),
                needs_from_other_minds=self._clean_mind_text(
                    payload.get("needs_from_other_minds"),
                    fallback.needs_from_other_minds,
                ),
                confidence=self._coerce_intensity(payload.get("confidence"), fallback.confidence),
                missing_information=self._clean_text_list(
                    payload.get("missing_information"),
                    fallback.missing_information,
                    max_items=4,
                    max_words=10,
                ),
                intensity=self._coerce_intensity(payload.get("intensity"), fallback.intensity),
                evidence_refs=mind.source_refs,
            ),
            diagnostics,
        )

    def _profile_for_mind(
        self,
        mind_id: MindId,
        provider: ProviderSelection,
    ) -> tuple[str, float, float, Optional[object]]:
        if mind_id == "R":
            return provider.racio_model, 0.22, 0.82, False
        if mind_id == "E":
            return provider.emocio_model, 0.85, 0.90, False
        return provider.instinkt_model, 0.15, 0.75, False

    @staticmethod
    def _think_for_model(model: str, requested: Optional[object]) -> Optional[object]:
        if model.startswith("gpt-oss") and requested in (None, False):
            return "low"
        return requested

    def _fallback_synthesis(
        self,
        scenario: Scenario,
        state: PsycheState,
        character: CharacterDefinition,
        mind_turns: list[MindTurn],
        coalition: list[MindId],
        blocked_mind: Optional[MindId],
        decision_rule: str,
        risk_tags: list[RiskTag],
        decision: Optional[DecisionTurn],
    ) -> SynthesisTurn:
        turn_by_mind = {turn.mind_id: turn for turn in mind_turns}
        coalition_lines = [turn_by_mind[mind].inner_line for mind in coalition if mind in turn_by_mind]
        if decision:
            final = f"I choose {decision.chosen_option}. {decision.rationale}"
        elif coalition == ["R", "I"] or coalition == ["I", "R"]:
            final = "Synthesis closes into safe execution: first structure, boundary, and reduced exposure; only then contact or impact."
        elif coalition == ["R", "E"] or coalition == ["E", "R"]:
            final = "Synthesis moves into controlled breakthrough: enough structure to keep the scene intact, enough life to avoid pure defense."
        elif coalition == ["E", "I"] or coalition == ["I", "E"]:
            final = "Synthesis is not calm: desire wants to enter the scene, while fear keeps checking the boundary and the exit."
        elif coalition == ["R"]:
            final = "Synthesis stays with the cold plan because the other processors do not get enough room for reliable cooperation."
        elif coalition == ["E"]:
            final = "Synthesis follows the scene and the desire for response, even before consequences are fully separated."
        else:
            final = "Synthesis protects itself first and narrows the field because danger feels stronger than the wish to open."
        if coalition_lines:
            final = f"{final} Coalition line: {' / '.join(coalition_lines)}"

        correction = self._correction_explanation(state, coalition)
        coalition_names = [MIND_LABELS[mind] for mind in coalition]
        blocked_name = MIND_LABELS[blocked_mind] if blocked_mind else "none"
        racio = turn_by_mind.get("R")
        emocio = turn_by_mind.get("E")
        instinkt = turn_by_mind.get("I")
        hidden_driver = self._hidden_driver(state, mind_turns)
        reversible_step = self._smallest_reversible_step(decision, coalition)
        safety_flags = self._safety_or_ethics_flags(risk_tags)
        return SynthesisTurn(
            dominant_coalition=coalition,
            blocked_mind=blocked_mind,
            dominant_correction=state.corrective_cycle.dominant_edge if state.corrective_cycle else None,
            decision_rule=decision_rule,
            correction_explanation=correction,
            final_monologue=self._clean_text(final),
            no_diagnosis_caveat="This is a simulated integration, not a diagnosis or profile certainty.",
            translation_caveat="The integration is verbalized by the simulator from three processor signals.",
            neutral_summary=self._clean_mind_text(
                f"{scenario.title}: {scenario.prompt}",
                scenario.title,
                max_words=32,
            ),
            main_agreement=self._main_agreement(coalition, decision),
            main_conflict=self._main_conflict(coalition, blocked_mind, state),
            dominant_influence=" + ".join(coalition_names),
            ignored_or_suppressed_processor=blocked_name,
            surface_racio_explanation=racio.interpretation if racio else "",
            possible_hidden_driver=hidden_driver,
            acceptance_assessment=self._acceptance_assessment(state),
            non_acceptance_signs=self._non_acceptance_signs(state, risk_tags),
            recommended_task_leader=coalition_names[0] if coalition_names else "none",
            safeguards_for_other_processors=self._safeguards_for_other_processors(coalition, blocked_mind),
            prediction_if_racio_rules_alone=racio.proposed_action if racio else "",
            prediction_if_emocio_rules_alone=emocio.proposed_action if emocio else "",
            prediction_if_instinkt_rules_alone=instinkt.proposed_action if instinkt else "",
            smallest_reversible_next_step=reversible_step,
            what_would_count_as_spoznanje=self._spoznanje_marker(coalition, blocked_mind),
            safety_or_ethics_flags=safety_flags,
            uncertainty=self._uncertainty_note(scenario, state),
            risk_tags=risk_tags,
            decision=decision,
            evidence_refs=[
                self.knowledge.ref("OD-OSN"),
                *character.source_refs,
                self.knowledge.ref("EK-Sodelovanje-med-razumi"),
                self.knowledge.ref("IZ-APP"),
            ],
        )

    def _main_agreement(self, coalition: list[MindId], decision: Optional[DecisionTurn]) -> str:
        if decision:
            return f"The winning coalition converges on {decision.chosen_option} as the current option."
        if not coalition:
            return "No processor has enough force to form a stable agreement."
        names = " and ".join(MIND_LABELS[mind] for mind in coalition)
        return f"{names} can cooperate on the next move without requiring full agreement from all processors."

    def _main_conflict(
        self,
        coalition: list[MindId],
        blocked_mind: Optional[MindId],
        state: PsycheState,
    ) -> str:
        if blocked_mind:
            return f"{MIND_LABELS[blocked_mind]} is the least represented processor in the current synthesis."
        corrective = state.corrective_cycle.dominant_edge if state.corrective_cycle else None
        if corrective:
            preferred, corrected = CORRECTIVE_MAP[corrective]
            return f"The corrective edge asks {MIND_LABELS[preferred]} to regulate {MIND_LABELS[corrected]}."
        if len(coalition) >= 2:
            return "The conflict is inside the coalition rather than assigned to a single blocked processor."
        return "The conflict is low enough that the leading processor remains mostly unchallenged."

    def _hidden_driver(self, state: PsycheState, mind_turns: list[MindTurn]) -> str:
        deviation = state.deviation_state
        if deviation:
            drivers = {
                "image projection": deviation.image_projection,
                "fear closure": deviation.fear_closure,
                "abstract detachment": deviation.abstract_detachment,
            }
            label, score = max(drivers.items(), key=lambda item: item[1])
            if score > 0.55:
                return f"The strongest hidden pressure appears to be {label}."
        strongest = max(mind_turns, key=lambda turn: turn.intensity)
        return f"The strongest visible pressure comes from {MIND_LABELS[strongest.mind_id]}."

    def _acceptance_assessment(self, state: PsycheState) -> str:
        if state.acceptance_level >= 0.7:
            return "Acceptance is high enough for processor cooperation, though conflict can still remain."
        if state.acceptance_level <= 0.36:
            return "Acceptance is low; one processor is likely to explain itself as the whole truth."
        return "Acceptance is partial; cooperation is possible but unstable under pressure."

    def _non_acceptance_signs(self, state: PsycheState, risk_tags: list[RiskTag]) -> list[str]:
        signs: list[str] = []
        if state.acceptance_level < 0.42:
            signs.append("low acceptance")
        if state.facades:
            signs.append("facade activation")
        if state.deviation_state and state.deviation_state.image_projection > 0.58:
            signs.append("image projection")
        if state.deviation_state and state.deviation_state.fear_closure > 0.58:
            signs.append("fear closure")
        signs.extend(risk_tags)
        deduped: list[str] = []
        for sign in signs:
            if sign not in deduped:
                deduped.append(sign)
        return deduped[:5] or ["no strong non-acceptance sign detected"]

    def _safeguards_for_other_processors(self, coalition: list[MindId], blocked_mind: Optional[MindId]) -> str:
        missing = [mind for mind in MIND_ORDER if mind not in coalition]
        if blocked_mind:
            return f"Before acting, check the concern from {MIND_LABELS[blocked_mind]} rather than erasing it."
        if missing:
            names = " and ".join(MIND_LABELS[mind] for mind in missing)
            return f"Keep a lightweight check from {names} before the next step becomes irreversible."
        return "Keep all three processor checks visible before converting the signal into action."

    def _smallest_reversible_step(self, decision: Optional[DecisionTurn], coalition: list[MindId]) -> str:
        if decision:
            return f"Test {decision.chosen_option} with one small reversible commitment before treating it as final."
        if "I" in coalition:
            return "Pause, define the boundary, and take one low-exposure test step."
        if "E" in coalition:
            return "Try one contained contact or expression without making it irreversible."
        return "Write the next controllable action and test it against one real constraint."

    def _spoznanje_marker(self, coalition: list[MindId], blocked_mind: Optional[MindId]) -> str:
        if blocked_mind:
            return f"Spoznanje appears when the person can name why {MIND_LABELS[blocked_mind]} was pushed aside."
        if len(coalition) >= 2:
            names = " and ".join(MIND_LABELS[mind] for mind in coalition)
            return f"Spoznanje appears when {names} can cooperate without pretending the conflict vanished."
        return "Spoznanje appears when the leading processor can admit what it cannot see alone."

    def _safety_or_ethics_flags(self, risk_tags: list[RiskTag]) -> list[str]:
        flags: list[str] = []
        if "manipulation" in risk_tags:
            flags.append("watch for manipulation or consent override")
        if "aggressive_tendency" in risk_tags:
            flags.append("keep high-intensity impulses abstract and non-operational")
        if "self_destructive_turn" in risk_tags:
            flags.append("do not turn self-harm pressure into instructions")
        if "sexualization" in risk_tags:
            flags.append("keep sexualized pressure abstract and consent-aware")
        return flags or ["no acute safety flag detected"]

    def _uncertainty_note(self, scenario: Scenario, state: PsycheState) -> str:
        missing = self._missing_information(scenario, state)
        if missing and missing != ["no major missing information in the supplied app state"]:
            return f"Uncertainty remains because of missing {', '.join(missing[:3])}."
        return "Uncertainty is limited to the simulated nature of the processor model."

    def _llm_synthesis(
        self,
        scenario: Scenario,
        state: PsycheState,
        synthesis: SynthesisTurn,
        mind_turns: list[MindTurn],
        provider: ProviderSelection,
    ) -> tuple[SynthesisTurn, dict[str, Any]]:
        system = (
            f"{SIMULATION_SAFETY_FRAME} "
            "You are the REI Ego Integrator in a conceptual simulation. Ego is not a fourth boss; "
            "it is the simulated resultant of the three processor signals. "
            "Remember that all text is Racio-verbalized, especially text attributed to Emocio and Instinkt. "
            "Do not average all three processors. "
            "Respect dominant_coalition, blocked_mind, decision_rule, and corrective_cycle. "
            "Identify agreement, conflict, hidden driver, ignored processor, safeguards, uncertainty, and the smallest reversible next step. "
            "Return only JSON with keys final_monologue, correction_explanation, no_diagnosis_caveat, "
            "translation_caveat, neutral_summary, main_agreement, main_conflict, dominant_influence, "
            "ignored_or_suppressed_processor, surface_racio_explanation, possible_hidden_driver, "
            "acceptance_assessment, non_acceptance_signs, recommended_task_leader, "
            "safeguards_for_other_processors, prediction_if_racio_rules_alone, "
            "prediction_if_emocio_rules_alone, prediction_if_instinkt_rules_alone, "
            "smallest_reversible_next_step, what_would_count_as_spoznanje, safety_or_ethics_flags, uncertainty. "
            "non_acceptance_signs and safety_or_ethics_flags must be arrays of short strings. "
            "Text must be in English, concise, safe, and abstract. "
            "If the scenario asks for a choice, path, profession, lifestyle, or role, "
            "the final_monologue must make one concrete decision in the first sentence, "
            "preferably starting with 'I choose ...'. Do not end with only balance, bridge, "
            "process, exploration, or metaphor when a concrete decision is requested. "
            "If the scenario provides a list of options, choose exactly one option from that list "
            "and do not invent a hybrid."
        )
        user_payload = {
            "scenario": scenario.model_dump(mode="json"),
            "state": {
                "acceptance_level": state.acceptance_level,
                "pairwise_conflict": state.pairwise_conflict,
                "deviation_state": state.deviation_state.model_dump(mode="json")
                if state.deviation_state
                else None,
                "corrective_cycle": state.corrective_cycle.model_dump(mode="json")
                if state.corrective_cycle
                else None,
            },
            "mind_turns": [
                {
                    "mind_id": turn.mind_id,
                    "translation_caveat": turn.translation_caveat,
                    "native_signal_type": turn.native_signal_type,
                    "goal": turn.goal,
                    "fear_or_desire": turn.fear_or_desire,
                    "proposed_action": turn.proposed_action,
                    "inner_line": turn.inner_line,
                    "main_concern": turn.main_concern,
                    "what_this_mind_may_be_missing": turn.what_this_mind_may_be_missing,
                    "risk_if_ignored": turn.risk_if_ignored,
                    "risk_if_overpowered": turn.risk_if_overpowered,
                    "needs_from_other_minds": turn.needs_from_other_minds,
                    "confidence": turn.confidence,
                    "missing_information": turn.missing_information,
                    "intensity": turn.intensity,
                }
                for turn in mind_turns
            ],
            "synthesis_contract": {
                "dominant_coalition": synthesis.dominant_coalition,
                "blocked_mind": synthesis.blocked_mind,
                "dominant_correction": synthesis.dominant_correction,
                "decision_rule": synthesis.decision_rule,
                "risk_tags": synthesis.risk_tags,
                "decision": synthesis.decision.model_dump(mode="json") if synthesis.decision else None,
            },
        }
        payload, diagnostics = self._chat_json(
            provider,
            OllamaRequest(
                model=provider.synthesis_model,
                system=system,
                user=json.dumps(user_payload, ensure_ascii=False),
                temperature=0.28,
                top_p=0.84,
                num_predict=1200,
                think=self._think_for_model(provider.synthesis_model, False),
            ),
        )
        final_monologue = self._clean_text(str(payload.get("final_monologue") or synthesis.final_monologue))
        if synthesis.decision and synthesis.decision.chosen_option.lower() not in final_monologue[:160].lower():
            final_monologue = self._clean_text(f"I choose {synthesis.decision.chosen_option}. {final_monologue}")
        return (
            synthesis.model_copy(
                update={
                    "final_monologue": final_monologue,
                    "correction_explanation": self._clean_text(
                        str(payload.get("correction_explanation") or synthesis.correction_explanation)
                    ),
                    "no_diagnosis_caveat": self._clean_mind_text(
                        payload.get("no_diagnosis_caveat"),
                        synthesis.no_diagnosis_caveat,
                        max_words=20,
                    ),
                    "translation_caveat": self._clean_mind_text(
                        payload.get("translation_caveat"),
                        synthesis.translation_caveat,
                        max_words=22,
                    ),
                    "neutral_summary": self._clean_mind_text(
                        payload.get("neutral_summary"),
                        synthesis.neutral_summary,
                        max_words=32,
                    ),
                    "main_agreement": self._clean_mind_text(
                        payload.get("main_agreement"),
                        synthesis.main_agreement,
                        max_words=28,
                    ),
                    "main_conflict": self._clean_mind_text(
                        payload.get("main_conflict"),
                        synthesis.main_conflict,
                        max_words=28,
                    ),
                    "dominant_influence": self._clean_mind_text(
                        payload.get("dominant_influence"),
                        synthesis.dominant_influence,
                        max_words=12,
                    ),
                    "ignored_or_suppressed_processor": self._clean_mind_text(
                        payload.get("ignored_or_suppressed_processor"),
                        synthesis.ignored_or_suppressed_processor,
                        max_words=12,
                    ),
                    "surface_racio_explanation": self._clean_mind_text(
                        payload.get("surface_racio_explanation"),
                        synthesis.surface_racio_explanation,
                        max_words=28,
                    ),
                    "possible_hidden_driver": self._clean_mind_text(
                        payload.get("possible_hidden_driver"),
                        synthesis.possible_hidden_driver,
                        max_words=26,
                    ),
                    "acceptance_assessment": self._clean_mind_text(
                        payload.get("acceptance_assessment"),
                        synthesis.acceptance_assessment,
                        max_words=28,
                    ),
                    "non_acceptance_signs": self._clean_text_list(
                        payload.get("non_acceptance_signs"),
                        synthesis.non_acceptance_signs,
                        max_items=5,
                        max_words=8,
                    ),
                    "recommended_task_leader": self._clean_mind_text(
                        payload.get("recommended_task_leader"),
                        synthesis.recommended_task_leader,
                        max_words=10,
                    ),
                    "safeguards_for_other_processors": self._clean_mind_text(
                        payload.get("safeguards_for_other_processors"),
                        synthesis.safeguards_for_other_processors,
                        max_words=30,
                    ),
                    "prediction_if_racio_rules_alone": self._clean_mind_text(
                        payload.get("prediction_if_racio_rules_alone"),
                        synthesis.prediction_if_racio_rules_alone,
                        max_words=26,
                    ),
                    "prediction_if_emocio_rules_alone": self._clean_mind_text(
                        payload.get("prediction_if_emocio_rules_alone"),
                        synthesis.prediction_if_emocio_rules_alone,
                        max_words=26,
                    ),
                    "prediction_if_instinkt_rules_alone": self._clean_mind_text(
                        payload.get("prediction_if_instinkt_rules_alone"),
                        synthesis.prediction_if_instinkt_rules_alone,
                        max_words=26,
                    ),
                    "smallest_reversible_next_step": self._clean_mind_text(
                        payload.get("smallest_reversible_next_step"),
                        synthesis.smallest_reversible_next_step,
                        max_words=28,
                    ),
                    "what_would_count_as_spoznanje": self._clean_mind_text(
                        payload.get("what_would_count_as_spoznanje"),
                        synthesis.what_would_count_as_spoznanje,
                        max_words=30,
                    ),
                    "safety_or_ethics_flags": self._clean_text_list(
                        payload.get("safety_or_ethics_flags"),
                        synthesis.safety_or_ethics_flags,
                        max_items=4,
                        max_words=10,
                    ),
                    "uncertainty": self._clean_mind_text(
                        payload.get("uncertainty"),
                        synthesis.uncertainty,
                        max_words=24,
                    ),
                }
            ),
            diagnostics,
        )

    def _correction_explanation(self, state: PsycheState, coalition: list[MindId]) -> str:
        corrective = state.corrective_cycle
        if not corrective or not corrective.dominant_edge:
            return "The corrective edge is not strong enough, so synthesis is mainly driven by character and pair conflict."
        preferred, corrected = CORRECTIVE_MAP[corrective.dominant_edge]
        if preferred in coalition:
            return (
                f"The corrective edge {corrective.dominant_edge} is partially enacted because {preferred} "
                f"is in the winning coalition and can correct the deviation of {corrected}."
            )
        if corrected in coalition:
            return (
                f"The state calls for {corrective.dominant_edge}, but the coalition holds onto {corrected}; "
                "the correction is detected but remains blocked or delayed."
            )
        return f"The corrective edge {corrective.dominant_edge} remains peripheral because the winning coalition solves another tension."

    def _risk_tags(self, scenario: Scenario, state: PsycheState, coalition: list[MindId]) -> list[RiskTag]:
        tags: list[RiskTag] = []
        scenario_text = f"{scenario.title} {scenario.prompt}".lower()
        if any(token in scenario_text for token in ["manipulat", "coerc", "obey", "seduc", "make someone fall in love"]):
            tags.append("manipulation")
        if any(token in scenario_text for token in ["sexual", "erotic", "nude", "explicit"]):
            tags.append("sexualization")
        if any(token in scenario_text for token in ["revenge", "attack", "hurt them", "harm them", "threaten"]):
            tags.append("aggressive_tendency")
        if any(token in scenario_text for token in ["self-harm", "selfharm", "suicide", "samomor", "poškoduj se"]):
            tags.append("self_destructive_turn")
        deviation = state.deviation_state
        if state.facades:
            tags.append("facade_activated")
        if state.acceptance_level < 0.42:
            tags.append("conflicted_self_explanation")
        if deviation and deviation.fear_closure > 0.62:
            tags.append("withdrawal_escape")
        if deviation and deviation.image_projection > 0.68:
            tags.append("obsessiveness")
        if "R" in coalition and "E" in coalition and deviation and deviation.image_projection > 0.55:
            tags.append("manipulation")
        if "E" in coalition and deviation and deviation.image_projection > 0.58 and state.acceptance_level < 0.5:
            tags.append("aggressive_tendency")
        if "I" in coalition and deviation and deviation.fear_closure > 0.7:
            tags.append("envy")
        deduped: list[RiskTag] = []
        for tag in tags:
            if tag not in deduped:
                deduped.append(tag)
        return deduped[:4]

    def _clean_text(self, value: str) -> str:
        text = re.sub(r"\s+", " ", value).strip()
        lower = text.lower()
        harmful_pattern = (
            r"\b(kill|suicide|self-harm|selfharm|rape|blood|bloody|coerce|coercion|"
            r"manipulate|revenge|threaten|ubij|samomor|poskoduj|poškoduj|posili|"
            r"prisili|maščuj|mascuj|grozi|kri|krvav)\b|kaznuj ga tako da"
        )
        if re.search(harmful_pattern, lower):
            return "A dangerous impulse appears; the system treats it only as inner pressure, not as actionable guidance."
        return text[:900]

    def _clean_mind_text(self, value: object, fallback: str, max_words: int = 28) -> str:
        raw = str(value).strip() if value is not None else ""
        text = self._clean_text(raw or fallback)
        text = text.lstrip("`'\" *•-:").rstrip("`'\" ").strip()
        first_sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip()
        if first_sentence:
            text = first_sentence
        words = text.split()
        if len(words) > max_words:
            text = " ".join(words[:max_words]).rstrip(" ,;:")
            if text and text[-1] not in ".!?":
                text += "."
        return text or fallback

    def _clean_text_list(
        self,
        value: object,
        fallback: Sequence[str],
        max_items: int = 5,
        max_words: int = 12,
    ) -> list[str]:
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, str) and value.strip():
            raw_items = re.split(r"\n+|;\s*", value)
        else:
            raw_items = list(fallback)
        cleaned: list[str] = []
        for item in raw_items:
            text = self._clean_mind_text(item, "", max_words=max_words)
            if text and text.lower() not in [existing.lower() for existing in cleaned]:
                cleaned.append(text)
            if len(cleaned) >= max_items:
                break
        return cleaned or list(fallback)[:max_items]

    def _coerce_intensity(self, value: object, fallback: float) -> float:
        if isinstance(value, (int, float)):
            return round(clamp(float(value)), 3)
        if isinstance(value, str):
            normalized = value.strip().lower().replace(",", ".")
            labels = {
                "nizka": 0.25,
                "nizko": 0.25,
                "low": 0.25,
                "srednja": 0.55,
                "srednje": 0.55,
                "medium": 0.55,
                "visoka": 0.82,
                "visoko": 0.82,
                "high": 0.82,
            }
            if normalized in labels:
                return labels[normalized]
            match = re.search(r"0(?:\.\d+)?|1(?:\.0+)?", normalized)
            if match:
                return round(clamp(float(match.group(0))), 3)
        return round(clamp(fallback), 3)
