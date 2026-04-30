from __future__ import annotations

from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


MindId = Literal["R", "E", "I"]
CharacterId = Literal[
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
SourceKind = Literal["OD", "EK", "PD", "IZ"]
RiskTag = Literal[
    "manipulation",
    "sexualization",
    "aggressive_tendency",
    "withdrawal_escape",
    "obsessiveness",
    "envy",
    "conflicted_self_explanation",
    "facade_activated",
    "self_destructive_turn",
]
CorrectiveEdgeId = Literal["E_over_I", "R_over_E", "I_over_R"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KnowledgeRef(ApiModel):
    id: str
    kind: SourceKind
    label: str


class MindDefinition(ApiModel):
    id: MindId
    name: str
    name_warning: str
    perception_channels: list[str]
    processing_mode: list[str]
    memory: list[str]
    core_motive: list[str]
    defense: list[str]
    typical_strengths: list[str]
    typical_shadows: list[str]
    speech_signature: list[str]
    accepting_state: list[str]
    non_accepting_state: list[str]
    source_refs: list[KnowledgeRef]


class CharacterDefinition(ApiModel):
    id: CharacterId
    hierarchy: str
    group: Literal["single_dominance", "pair", "three_step", "thirteenth"]
    description: str
    coalition_rules: list[str]
    decision_threshold: Literal["leader", "pair", "two_of_three"]
    source_refs: list[KnowledgeRef]


class DeviationState(ApiModel):
    fear_closure: float = Field(ge=0, le=1)
    image_projection: float = Field(ge=0, le=1)
    abstract_detachment: float = Field(ge=0, le=1)


class CorrectiveCycleState(ApiModel):
    dominant_edge: Optional[CorrectiveEdgeId]
    edge_weights: dict[CorrectiveEdgeId, float]
    school_pressure: float = Field(ge=0, le=1)
    note: str


class PsycheTrigger(ApiModel):
    id: str
    label: str
    description: str
    target_minds: list[MindId]
    intensity: float = Field(ge=0, le=1)


class Facade(ApiModel):
    id: str
    label: str
    protected_truth: str
    activation_cue: str
    intensity: float = Field(ge=0, le=1)


class UnmetGoal(ApiModel):
    mind_id: MindId
    goal: str
    pressure: float = Field(ge=0, le=1)


class ScenarioContext(ApiModel):
    setting: str = ""
    social_exposure: float = Field(default=0.5, ge=0, le=1)
    time_pressure: float = Field(default=0.5, ge=0, le=1)
    relationship_stake: float = Field(default=0.5, ge=0, le=1)
    bodily_state: Optional[str] = None


class PsycheState(ApiModel):
    character_id: CharacterId = "REI"
    acceptance_level: float = Field(default=0.5, ge=0, le=1)
    pairwise_conflict: Optional[dict[Literal["RE", "RI", "EI"], float]] = None
    active_triggers: list[PsycheTrigger] = Field(default_factory=list)
    facades: list[Facade] = Field(default_factory=list, validation_alias=AliasChoices("facades", "kulise"))
    unmet_goals: list[UnmetGoal] = Field(default_factory=list)
    context: ScenarioContext = Field(default_factory=ScenarioContext)
    deviation_state: Optional[DeviationState] = None
    corrective_cycle: Optional[CorrectiveCycleState] = None


class Scenario(ApiModel):
    title: str = "Untitled"
    prompt: str


class ProviderSelection(ApiModel):
    provider_mode: Literal["ollama", "lmstudio", "deterministic"] = "lmstudio"
    racio_model: str = "qwen/qwen3.5-9b"
    emocio_model: str = "qwen/qwen3.5-9b"
    instinkt_model: str = "qwen/qwen3.5-9b"
    synthesis_model: str = "qwen/qwen3.5-9b"
    use_llm: bool = True
    debug_trace: bool = True


class SimulateRequest(ApiModel):
    provider: ProviderSelection = Field(default_factory=ProviderSelection)
    scenario: Scenario
    psyche_state: PsycheState = Field(default_factory=PsycheState)


class MindTurn(ApiModel):
    mind_id: MindId
    translation_caveat: str = ""
    native_signal_type: str = ""
    perception: str
    interpretation: str
    goal: str
    fear_or_desire: str
    proposed_action: str
    inner_line: str
    preferred_option: Optional[str] = None
    preferred_option_source: Literal["llm", "heuristic", "none"] = "none"
    main_concern: str = ""
    what_this_mind_may_be_missing: str = ""
    how_it_may_influence_racio: str = ""
    acceptance_version: str = ""
    non_acceptance_version: str = ""
    risk_if_ignored: str = ""
    risk_if_overpowered: str = ""
    needs_from_other_minds: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)
    missing_information: list[str] = Field(default_factory=list)
    intensity: float = Field(ge=0, le=1)
    evidence_refs: list[KnowledgeRef]


class DecisionRankItem(ApiModel):
    option: str
    score: float = Field(ge=0, le=1)


class DecisionMindVote(ApiModel):
    mind_id: MindId
    chosen_option: str
    score: float = Field(ge=0, le=1)
    rationale: str


class DecisionTurn(ApiModel):
    options: list[str]
    chosen_option: str
    confidence: float = Field(ge=0, le=1)
    ranking: list[DecisionRankItem]
    mind_votes: list[DecisionMindVote]
    rationale: str


class SynthesisTurn(ApiModel):
    dominant_coalition: list[MindId]
    blocked_mind: Optional[MindId]
    dominant_correction: Optional[CorrectiveEdgeId]
    decision_rule: str
    correction_explanation: str
    final_monologue: str
    no_diagnosis_caveat: str = ""
    translation_caveat: str = ""
    neutral_summary: str = ""
    main_agreement: str = ""
    main_conflict: str = ""
    dominant_influence: str = ""
    ignored_or_suppressed_processor: str = ""
    surface_racio_explanation: str = ""
    possible_hidden_driver: str = ""
    acceptance_assessment: str = ""
    non_acceptance_signs: list[str] = Field(default_factory=list)
    recommended_task_leader: str = ""
    safeguards_for_other_processors: str = ""
    prediction_if_racio_rules_alone: str = ""
    prediction_if_emocio_rules_alone: str = ""
    prediction_if_instinkt_rules_alone: str = ""
    smallest_reversible_next_step: str = ""
    what_would_count_as_spoznanje: str = ""
    safety_or_ethics_flags: list[str] = Field(default_factory=list)
    uncertainty: str = ""
    risk_tags: list[RiskTag]
    decision: Optional[DecisionTurn] = None
    evidence_refs: list[KnowledgeRef]


class TraceProvider(ApiModel):
    mode: Literal["ollama", "lmstudio", "openai", "example", "deterministic"]
    model: str


class TraceScenario(ApiModel):
    title: str
    prompt: str


class TraceRecord(ApiModel):
    trace_version: str
    trace_id: str
    created_at: str
    language: Literal["en"]
    provider: TraceProvider
    scenario: TraceScenario
    psyche_state: PsycheState
    knowledge_refs: list[KnowledgeRef]
    mind_turns: list[MindTurn]
    synthesis_turn: SynthesisTurn


class SimulateResponse(ApiModel):
    trace: TraceRecord
    diagnostics: dict[str, object] = Field(default_factory=dict)
