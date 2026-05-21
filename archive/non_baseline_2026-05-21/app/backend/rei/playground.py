from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Iterator, Optional

from pydantic import Field

from .engine import ReiEngine
from .knowledge import KnowledgeIndex
from .models import AcceptanceMode, ApiModel, ProviderSelection, REICycleResponse, Scenario
from .profiles import profile_leader_label, profile_weights
from .prompts import EGO_SYSTEM_PROMPT, PROCESSOR_PROMPTS
from .providers import LMStudioProvider, OllamaProvider


SAFETY_FRAMING = (
    "This is a conceptual REI-inspired simulation, not diagnosis, therapy, "
    "personality typing, or proof of actual inner structure."
)

PLAYGROUND_PROFILES = [
    "R",
    "E",
    "I",
    "RE",
    "RI",
    "EI",
    "R>E>I",
    "R>I>E",
    "E>R>I",
    "E>I>R",
    "I>R>E",
    "I>E>R",
    "REI",
]

MIND_NAMES = {"R": "racio", "E": "emocio", "I": "instinkt"}
MIND_LABELS = {"R": "Racio", "E": "Emocio", "I": "Instinkt"}


class PlaygroundStakes(ApiModel):
    financial_risk: Optional[float] = None
    social_exposure: Optional[float] = None
    time_pressure: Optional[float] = None
    relationship_risk: Optional[float] = None
    reversibility: Optional[float] = None


class PlaygroundScenario(ApiModel):
    title: str = "Untitled"
    situation: str
    decision_options: list[str] = Field(default_factory=list)
    stakes: PlaygroundStakes = Field(default_factory=PlaygroundStakes)


class PlaygroundRequest(ApiModel):
    provider: ProviderSelection = Field(
        default_factory=lambda: ProviderSelection(
            provider_mode="ollama",
            racio_model="granite4.1:30b",
            emocio_model="granite4.1:30b",
            instinkt_model="granite4.1:30b",
            synthesis_model="granite4.1:30b",
            use_llm=True,
            debug_trace=True,
        )
    )
    scenario: PlaygroundScenario
    profile: str = "REI"
    compare_profiles: list[str] = Field(default_factory=list)
    user_notes: str = ""
    acceptance_mode: AcceptanceMode = "unknown"
    use_memory: bool = True
    save_observation: bool = True


class OptionEvaluation(ApiModel):
    option: str
    racio_score: float
    emocio_score: float
    instinkt_score: float
    racio_evaluation: str
    emocio_evaluation: str
    instinkt_evaluation: str
    ego_pressure: str
    likely_selected_option: str
    is_likely_selected: bool
    rejected_option_reason: str


class TrialogueLine(ApiModel):
    processor: str
    label: str
    caveat: str
    signal: str


class TrialogueRound(ApiModel):
    round: int
    title: str
    lines: list[TrialogueLine]


class TrialogueFinal(ApiModel):
    perceived_world: str
    action_tendency: str


class PlaygroundTrialogue(ApiModel):
    rounds: list[TrialogueRound]
    final: TrialogueFinal


class ProfileComparison(ApiModel):
    profile: str
    canonical_profile: str
    profile_leader: str
    situational_driver: str
    resultant_leader_under_pressure: str
    selected_option: str
    perceived_world: str
    hidden_driver: str
    smallest_next_step: str


class ProcessorRunInstruction(ApiModel):
    processor: str
    label: str
    model: str
    system_instruction: str
    user_payload: str = ""
    provider_options: dict[str, Any] = Field(default_factory=dict)


class PlaygroundRunResponse(ApiModel):
    safety_framing: str
    timestamp: str
    scenario: PlaygroundScenario
    selected_profile: str
    canonical_profile: str
    options: list[str]
    processor_outputs: REICycleResponse
    option_evaluations: list[OptionEvaluation]
    trialogue: PlaygroundTrialogue
    compare_profiles: list[ProfileComparison]
    processor_instructions: list[ProcessorRunInstruction] = Field(default_factory=list)
    observation_path: Optional[str]
    user_notes: str = ""


EventEmitter = Callable[[str, dict[str, Any]], None]


def build_playground_response(
    engine: ReiEngine,
    request: PlaygroundRequest,
    root_dir: Path,
    emit: Optional[EventEmitter] = None,
) -> PlaygroundRunResponse:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    scenario = _cycle_scenario(request.scenario)
    selected_profile = _normalize_public_profile(request.profile)
    canonical_profile, weights = profile_weights(selected_profile)

    _emit(emit, "status", {"message": f"Running selected profile {selected_profile}", "profile": selected_profile})
    _emit(
        emit,
        "processor_instructions",
        {
            "instructions": [
                item.model_dump(mode="json")
                for item in build_processor_instructions({}, request.provider)
            ]
        },
    )
    cycle, diagnostics = engine.run_rei_cycle(
        user_prompt=scenario.prompt,
        character_profile=selected_profile,
        acceptance_mode=request.acceptance_mode,  # type: ignore[arg-type]
        rounds=3,
        stream=True,
        use_memory=request.use_memory,
        provider=request.provider,
    )

    options = _clean_options(request.scenario.decision_options)
    option_evaluations = evaluate_options(options, weights, cycle, request.scenario.stakes)
    trialogue = build_trialogue(cycle)
    processor_instructions = build_processor_instructions(diagnostics, request.provider)

    comparisons: list[ProfileComparison] = []
    comparison_profiles = [
        profile
        for profile in [_normalize_public_profile(profile) for profile in request.compare_profiles]
        if profile in PLAYGROUND_PROFILES
    ]
    for profile in dict.fromkeys(comparison_profiles):
        _emit(emit, "status", {"message": f"Comparing profile {profile}", "profile": profile})
        if profile == selected_profile:
            profile_cycle = cycle
        else:
            profile_cycle, _ = engine.run_rei_cycle(
                user_prompt=scenario.prompt,
                character_profile=profile,
                acceptance_mode=request.acceptance_mode,  # type: ignore[arg-type]
                rounds=3,
                stream=True,
                use_memory=request.use_memory,
                provider=request.provider,
            )
        comparison = build_profile_comparison(profile, profile_cycle, options, request.scenario.stakes)
        comparisons.append(comparison)
        _emit(emit, "compare_result", comparison.model_dump(mode="json"))

    response = PlaygroundRunResponse(
        safety_framing=SAFETY_FRAMING,
        timestamp=timestamp,
        scenario=request.scenario,
        selected_profile=selected_profile,
        canonical_profile=canonical_profile,
        options=options,
        processor_outputs=cycle,
        option_evaluations=option_evaluations,
        trialogue=trialogue,
        compare_profiles=comparisons,
        processor_instructions=processor_instructions,
        observation_path=None,
        user_notes=request.user_notes,
    )
    if request.save_observation:
        path = save_observation(root_dir, response)
        response = response.model_copy(update={"observation_path": str(path)})
    return response


def stream_playground_response(knowledge: KnowledgeIndex, request: PlaygroundRequest, root_dir: Path) -> Iterator[str]:
    queue: Queue[Optional[tuple[str, dict[str, Any]]]] = Queue()

    def emit(event: str, data: dict[str, Any]) -> None:
        queue.put((event, data))

    def provider_callback(event: dict[str, Any]) -> None:
        emit("token", event)

    def worker() -> None:
        try:
            ollama = OllamaProvider()
            lmstudio = LMStudioProvider()
            if request.provider.provider_mode == "ollama" and request.provider.use_llm:
                ollama.stream_responses = True
                ollama.stream_callback = provider_callback
            engine = ReiEngine(knowledge=knowledge, ollama=ollama, lmstudio=lmstudio)
            emit("status", {"message": "Playground run started", "safety_framing": SAFETY_FRAMING})
            response = build_playground_response(engine, request, root_dir, emit=emit)
            emit("result", response.model_dump(mode="json"))
        except Exception as exc:
            emit("error", {"message": str(exc), "safety_framing": SAFETY_FRAMING})
        finally:
            queue.put(None)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    while True:
        item = queue.get()
        if item is None:
            break
        event, data = item
        yield _sse(event, data)


def list_observations(root_dir: Path, limit: int = 30) -> list[dict[str, Any]]:
    observation_dir = root_dir / "output" / "observations"
    if not observation_dir.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(observation_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        items.append(
            {
                "id": path.name,
                "path": str(path),
                "timestamp": payload.get("timestamp"),
                "title": payload.get("scenario", {}).get("title"),
                "selected_profile": payload.get("selected_profile"),
                "selected_option": _selected_option_from_log(payload),
                "user_notes": payload.get("user_notes", ""),
                "safety_framing": payload.get("safety_framing", SAFETY_FRAMING),
            }
        )
    return items


def load_observation(root_dir: Path, observation_id: str) -> dict[str, Any]:
    observation_dir = (root_dir / "output" / "observations").resolve()
    path = (observation_dir / observation_id).resolve()
    if path.parent != observation_dir or path.suffix.lower() != ".json":
        raise ValueError("Invalid observation id")
    if not path.exists():
        raise FileNotFoundError(observation_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("safety_framing", SAFETY_FRAMING)
    payload.setdefault("processor_instructions", [])
    return payload


def build_processor_instructions(
    diagnostics: dict[str, Any],
    provider: ProviderSelection,
) -> list[ProcessorRunInstruction]:
    calls = diagnostics.get("llm_calls", [])
    by_role: dict[str, dict[str, Any]] = {}
    if isinstance(calls, list):
        for call in calls:
            if not isinstance(call, dict):
                continue
            role = _instruction_role_from_label(str(call.get("label") or ""))
            if role and role not in by_role:
                by_role[role] = call

    return [
        _processor_instruction("racio", "Racio", provider, by_role.get("racio")),
        _processor_instruction(
            "emocio",
            "Emocio (Racio-translated non-verbal signal)",
            provider,
            by_role.get("emocio"),
        ),
        _processor_instruction(
            "instinkt",
            "Instinkt (Racio-translated non-verbal signal)",
            provider,
            by_role.get("instinkt"),
        ),
        _processor_instruction("ego", "EgoResultant", provider, by_role.get("ego")),
    ]


def evaluate_options(
    options: list[str],
    weights: dict[str, float],
    cycle: REICycleResponse,
    stakes: PlaygroundStakes,
) -> list[OptionEvaluation]:
    if not options:
        return []
    scored = [_score_option(option, stakes) for option in options]
    weighted_scores = {
        option: (
            scores["R"] * weights.get("racio", 0.0)
            + scores["E"] * weights.get("emocio", 0.0)
            + scores["I"] * weights.get("instinkt", 0.0)
        )
        for option, scores in scored
    }
    selected = max(options, key=lambda option: weighted_scores.get(option, 0.0))
    selected_score = weighted_scores[selected]
    ego = cycle.ego_resultant
    evaluations: list[OptionEvaluation] = []
    for option, scores in scored:
        is_selected = option == selected
        gap = max(0.0, selected_score - weighted_scores[option])
        evaluations.append(
            OptionEvaluation(
                option=option,
                racio_score=round(scores["R"], 3),
                emocio_score=round(scores["E"], 3),
                instinkt_score=round(scores["I"], 3),
                racio_evaluation=_mind_evaluation("R", option, scores["R"], cycle),
                emocio_evaluation=_mind_evaluation("E", option, scores["E"], cycle),
                instinkt_evaluation=_mind_evaluation("I", option, scores["I"], cycle),
                ego_pressure=(
                    f"{ego.resultant_leader_under_pressure} pressure reads this through "
                    f"{ego.situational_driver}; weighted score {weighted_scores[option]:.2f}."
                ),
                likely_selected_option=selected,
                is_likely_selected=is_selected,
                rejected_option_reason=(
                    "Current likely selection under this profile."
                    if is_selected
                    else _rejection_reason(option, scores, gap, selected)
                ),
            )
        )
    return evaluations


def build_trialogue(cycle: REICycleResponse) -> PlaygroundTrialogue:
    racio = cycle.signals.racio
    emocio = cycle.signals.emocio_translated
    instinkt = cycle.signals.instinkt_translated
    return PlaygroundTrialogue(
        rounds=[
            TrialogueRound(
                round=1,
                title="Each processor states its signal",
                lines=[
                    TrialogueLine(
                        processor="racio",
                        label="Racio",
                        caveat="Conscious verbal-analytical simulated signal.",
                        signal=f"{racio.perception} Preferred action: {racio.preferred_action}",
                    ),
                    TrialogueLine(
                        processor="emocio",
                        label="Emocio (Racio-translated non-verbal signal)",
                        caveat="Not a literal conscious speaker; this is Racio's verbal approximation.",
                        signal=f"{emocio.desired_image} Preferred pressure: {emocio.preferred_action}",
                    ),
                    TrialogueLine(
                        processor="instinkt",
                        label="Instinkt (Racio-translated non-verbal signal)",
                        caveat="Not a literal conscious speaker; this is Racio's verbal approximation.",
                        signal=f"{instinkt.threat_map} Preferred pressure: {instinkt.preferred_action}",
                    ),
                ],
            ),
            TrialogueRound(
                round=2,
                title="Each processor objects to or conditions the others",
                lines=[
                    TrialogueLine(
                        processor="racio",
                        label="Racio",
                        caveat="Conscious verbal-analytical simulated signal.",
                        signal=f"Objects to unclear evidence: {racio.rationalization_risk}",
                    ),
                    TrialogueLine(
                        processor="emocio",
                        label="Emocio (Racio-translated non-verbal signal)",
                        caveat="Not a literal conscious speaker; this is Racio's verbal approximation.",
                        signal=f"Conditions the decision on dignity and image: {emocio.pride_or_shame}",
                    ),
                    TrialogueLine(
                        processor="instinkt",
                        label="Instinkt (Racio-translated non-verbal signal)",
                        caveat="Not a literal conscious speaker; this is Racio's verbal approximation.",
                        signal=f"Objects to unsafe exposure: {instinkt.boundary_issue}",
                    ),
                ],
            ),
            TrialogueRound(
                round=3,
                title="Each processor states the condition for acceptability",
                lines=[
                    TrialogueLine(
                        processor="racio",
                        label="Racio",
                        caveat="Conscious verbal-analytical simulated signal.",
                        signal=f"Acceptable if sequence and unknowns are handled: {racio.timeline_or_sequence}",
                    ),
                    TrialogueLine(
                        processor="emocio",
                        label="Emocio (Racio-translated non-verbal signal)",
                        caveat="Not a literal conscious speaker; this is Racio's verbal approximation.",
                        signal=f"Acceptable if expression stays dignified: {emocio.accepted_expression}",
                    ),
                    TrialogueLine(
                        processor="instinkt",
                        label="Instinkt (Racio-translated non-verbal signal)",
                        caveat="Not a literal conscious speaker; this is Racio's verbal approximation.",
                        signal=f"Acceptable if the safety condition is met: {instinkt.minimum_safety_condition}",
                    ),
                ],
            ),
        ],
        final=TrialogueFinal(
            perceived_world=cycle.ego_resultant.perceived_world,
            action_tendency=cycle.ego_resultant.action_tendency
            or cycle.ego_resultant.likely_action_under_pressure,
        ),
    )


def build_profile_comparison(
    profile: str,
    cycle: REICycleResponse,
    options: list[str],
    stakes: PlaygroundStakes,
) -> ProfileComparison:
    canonical_profile, weights = profile_weights(profile)
    evaluations = evaluate_options(options, weights, cycle, stakes)
    selected = evaluations[0].likely_selected_option if evaluations else ""
    ego = cycle.ego_resultant
    return ProfileComparison(
        profile=profile,
        canonical_profile=canonical_profile,
        profile_leader=profile_leader_label(weights),
        situational_driver=ego.situational_driver,
        resultant_leader_under_pressure=ego.resultant_leader_under_pressure,
        selected_option=selected,
        perceived_world=ego.perceived_world,
        hidden_driver=ego.hidden_driver,
        smallest_next_step=ego.smallest_acceptable_next_step,
    )


def save_observation(root_dir: Path, response: PlaygroundRunResponse) -> Path:
    observation_dir = root_dir / "output" / "observations"
    observation_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    slug = _slug(response.scenario.title or "scenario")
    profile = _slug(response.selected_profile)
    path = observation_dir / f"{timestamp}_{slug}_{profile}.json"
    payload = response.model_dump(mode="json")
    payload["observation_path"] = str(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _cycle_scenario(scenario: PlaygroundScenario) -> Scenario:
    options = _clean_options(scenario.decision_options)
    option_sentence = ""
    if options:
        if len(options) == 1:
            joined = options[0]
        else:
            joined = f"{', '.join(options[:-1])}, or {options[-1]}"
        option_sentence = f"\nThe person must choose from this list: {joined}."
    stakes = _stakes_sentence(scenario.stakes)
    prompt = f"{scenario.situation.strip()}{option_sentence}{stakes}"
    return Scenario(title=scenario.title.strip() or "Untitled", prompt=prompt.strip())


def _stakes_sentence(stakes: PlaygroundStakes) -> str:
    parts = []
    for key, value in stakes.model_dump(mode="json").items():
        if value is not None:
            parts.append(f"{key}={float(value):.2f}")
    return f"\nStakes: {', '.join(parts)}." if parts else ""


def _clean_options(options: list[str]) -> list[str]:
    cleaned: list[str] = []
    for option in options:
        text = re.sub(r"\s+", " ", option).strip(" \t\r\n.;")
        if text and text.lower() not in [existing.lower() for existing in cleaned]:
            cleaned.append(text[:120])
    return cleaned[:12]


def _score_option(option: str, stakes: PlaygroundStakes) -> tuple[str, dict[str, float]]:
    text = option.lower()
    scores = {"R": 0.46, "E": 0.46, "I": 0.46}

    def bump(mind: str, value: float) -> None:
        scores[mind] = max(scores[mind], value)

    if any(token in text for token in ["pilot", "90-day", "90 day", "while employed", "test", "trial"]):
        bump("R", 0.9)
        bump("E", 0.62)
        bump("I", 0.84)
    if any(token in text for token in ["mentor", "investor", "advisor", "feedback", "partner"]):
        bump("R", 0.76)
        bump("E", 0.78)
        bump("I", 0.64)
    if any(token in text for token in ["quit", "immediately", "all in", "resign", "launch now"]):
        bump("R", 0.42)
        bump("E", 0.9)
        bump("I", 0.18)
    if any(token in text for token in ["drop", "stop", "abandon", "cancel"]):
        bump("R", 0.5)
        bump("E", 0.18)
        bump("I", 0.88)
    if any(token in text for token in ["plan", "budget", "research", "validate", "measure"]):
        bump("R", 0.84)
    if any(token in text for token in ["public", "announce", "pitch", "visible", "brand"]):
        bump("E", 0.82)
    if any(token in text for token in ["safe", "boundary", "protect", "employed", "reversible"]):
        bump("I", 0.86)

    financial = _stake(stakes.financial_risk)
    relationship = _stake(stakes.relationship_risk)
    time_pressure = _stake(stakes.time_pressure)
    reversibility = _stake(stakes.reversibility)
    risk = financial * 0.55 + relationship * 0.25 + time_pressure * 0.2
    irreversible = any(token in text for token in ["quit", "immediately", "drop", "abandon", "all in"])
    reversible = any(token in text for token in ["pilot", "test", "while employed", "mentor", "advisor", "reversible"])

    if irreversible:
        scores["I"] -= 0.36 * risk
        scores["R"] -= 0.18 * financial
    if reversible:
        scores["I"] += 0.22 * max(reversibility, 0.4)
        scores["R"] += 0.12
    if time_pressure > 0.65 and any(token in text for token in ["immediately", "now"]):
        scores["E"] += 0.08
        scores["R"] -= 0.06

    return option, {mind: round(_clamp(value), 3) for mind, value in scores.items()}


def _mind_evaluation(mind: str, option: str, score: float, cycle: REICycleResponse) -> str:
    if mind == "R":
        anchor = cycle.signals.racio.utility_model or cycle.signals.racio.preferred_action
        return f"Racio rates {option} at {score:.2f}: sequence, evidence, and control are checked against {anchor}"
    if mind == "E":
        anchor = cycle.signals.emocio_translated.desired_image or cycle.signals.emocio_translated.preferred_action
        return (
            f"Emocio rates {option} at {score:.2f}: Racio-translated image/social pressure "
            f"checks aliveness and dignity against {anchor}"
        )
    anchor = cycle.signals.instinkt_translated.minimum_safety_condition
    return (
        f"Instinkt rates {option} at {score:.2f}: Racio-translated protective pressure "
        f"checks exposure, loss, and boundary against {anchor}"
    )


def _rejection_reason(option: str, scores: dict[str, float], gap: float, selected: str) -> str:
    weakest = min(scores, key=scores.get)
    if weakest == "I":
        reason = "protective safety pressure is too low"
    elif weakest == "E":
        reason = "image/aliveness pressure is too low"
    else:
        reason = "sequence or evidence pressure is too low"
    return f"Rejected against {selected} because {reason}; weighted gap {gap:.2f}."


def _selected_option_from_log(payload: dict[str, Any]) -> str:
    for item in payload.get("option_evaluations", []):
        if item.get("is_likely_selected"):
            return str(item.get("option") or "")
    return ""


def _normalize_public_profile(profile: str) -> str:
    compact = "".join((profile or "REI").split())
    return compact if compact in PLAYGROUND_PROFILES else "REI"


def _stake(value: Optional[float]) -> float:
    return 0.5 if value is None else _clamp(float(value))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-").lower()
    return slug[:60] or "rei"


def _emit(emit: Optional[EventEmitter], event: str, data: dict[str, Any]) -> None:
    if emit is not None:
        emit(event, data)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _processor_instruction(
    role: str,
    label: str,
    provider: ProviderSelection,
    call: Optional[dict[str, Any]],
) -> ProcessorRunInstruction:
    request = call.get("request", {}) if isinstance(call, dict) else {}
    request = request if isinstance(request, dict) else {}
    provider_options = request.get("options", {})
    if not isinstance(provider_options, dict):
        provider_options = {}
    user_payload = _pretty_payload(request.get("user"))
    system_instruction = str(request.get("system") or _fallback_system_instruction(role))
    model = str(call.get("model")) if isinstance(call, dict) and call.get("model") else _configured_model(role, provider)
    return ProcessorRunInstruction(
        processor=role,
        label=label,
        model=model,
        system_instruction=system_instruction,
        user_payload=user_payload,
        provider_options=dict(provider_options),
    )


def _instruction_role_from_label(label: str) -> Optional[str]:
    normalized = label.lower().split(":", 1)[0]
    if normalized in {"racio", "emocio", "instinkt"}:
        return normalized
    if normalized in {"ego", "ego_resultant", "s"}:
        return "ego"
    return None


def _fallback_system_instruction(role: str) -> str:
    if role == "ego":
        return EGO_SYSTEM_PROMPT
    return PROCESSOR_PROMPTS.get(role, "")


def _configured_model(role: str, provider: ProviderSelection) -> str:
    if provider.provider_mode not in {"ollama", "lmstudio"} or not provider.use_llm:
        return "deterministic fallback"
    if role == "racio":
        return provider.racio_model
    if role == "emocio":
        return provider.emocio_model
    if role == "instinkt":
        return provider.instinkt_model
    return provider.synthesis_model


def _pretty_payload(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return value
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    return json.dumps(value, ensure_ascii=False, indent=2)
