export type MindId = "R" | "E" | "I";
export type CharacterId =
  | "R"
  | "E"
  | "I"
  | "RE"
  | "RI"
  | "EI"
  | "R>E>I"
  | "R>I>E"
  | "E>R>I"
  | "E>I>R"
  | "I>R>E"
  | "I>E>R"
  | "REI";

export type CorrectiveEdgeId = "E_over_I" | "R_over_E" | "I_over_R";

export interface KnowledgeRef {
  id: string;
  kind: "OD" | "EK" | "PD" | "IZ";
  label: string;
}

export interface CharacterDefinition {
  id: CharacterId;
  hierarchy: string;
  group: "single_dominance" | "pair" | "three_step" | "thirteenth";
  description: string;
  coalition_rules: string[];
  decision_threshold: "leader" | "pair" | "two_of_three";
  source_refs: KnowledgeRef[];
}

export interface ScenarioContext {
  setting: string;
  social_exposure: number;
  time_pressure: number;
  relationship_stake: number;
  bodily_state?: string;
}

export interface PsycheState {
  character_id: CharacterId;
  acceptance_level: number;
  pairwise_conflict?: Record<"RE" | "RI" | "EI", number>;
  active_triggers: Array<{
    id: string;
    label: string;
    description: string;
    target_minds: MindId[];
    intensity: number;
  }>;
  facades: Array<{
    id: string;
    label: string;
    protected_truth: string;
    activation_cue: string;
    intensity: number;
  }>;
  unmet_goals: Array<{
    mind_id: MindId;
    goal: string;
    pressure: number;
  }>;
  context: ScenarioContext;
  deviation_state?: {
    fear_closure: number;
    image_projection: number;
    abstract_detachment: number;
  };
  corrective_cycle?: {
    dominant_edge: CorrectiveEdgeId | null;
    edge_weights: Record<CorrectiveEdgeId, number>;
    school_pressure: number;
    note: string;
  };
}

export interface MindTurn {
  mind_id: MindId;
  translation_caveat?: string;
  native_signal_type?: string;
  perception: string;
  interpretation: string;
  goal: string;
  fear_or_desire: string;
  proposed_action: string;
  inner_line: string;
  preferred_option?: string | null;
  preferred_option_source?: "llm" | "heuristic" | "none";
  main_concern?: string;
  what_this_mind_may_be_missing?: string;
  how_it_may_influence_racio?: string;
  acceptance_version?: string;
  non_acceptance_version?: string;
  risk_if_ignored?: string;
  risk_if_overpowered?: string;
  needs_from_other_minds?: string;
  confidence?: number;
  missing_information?: string[];
  intensity: number;
  evidence_refs: KnowledgeRef[];
}

export interface SynthesisTurn {
  dominant_coalition: MindId[];
  blocked_mind: MindId | null;
  dominant_correction: CorrectiveEdgeId | null;
  decision_rule: string;
  correction_explanation: string;
  final_monologue: string;
  no_diagnosis_caveat?: string;
  translation_caveat?: string;
  neutral_summary?: string;
  main_agreement?: string;
  main_conflict?: string;
  dominant_influence?: string;
  ignored_or_suppressed_processor?: string;
  surface_racio_explanation?: string;
  possible_hidden_driver?: string;
  acceptance_assessment?: string;
  non_acceptance_signs?: string[];
  recommended_task_leader?: string;
  safeguards_for_other_processors?: string;
  prediction_if_racio_rules_alone?: string;
  prediction_if_emocio_rules_alone?: string;
  prediction_if_instinkt_rules_alone?: string;
  smallest_reversible_next_step?: string;
  what_would_count_as_spoznanje?: string;
  safety_or_ethics_flags?: string[];
  uncertainty?: string;
  risk_tags: string[];
  decision?: {
    options: string[];
    chosen_option: string;
    confidence: number;
    ranking: Array<{
      option: string;
      score: number;
    }>;
    mind_votes: Array<{
      mind_id: MindId;
      chosen_option: string;
      score: number;
      rationale: string;
    }>;
    rationale: string;
  } | null;
  evidence_refs: KnowledgeRef[];
}

export interface TraceRecord {
  trace_version: string;
  trace_id: string;
  created_at: string;
  language: "en";
  provider: {
    mode: string;
    model: string;
  };
  scenario: {
    title: string;
    prompt: string;
  };
  psyche_state: PsycheState;
  knowledge_refs: KnowledgeRef[];
  mind_turns: MindTurn[];
  synthesis_turn: SynthesisTurn;
}

export interface ProviderSelection {
  provider_mode: "ollama" | "lmstudio" | "deterministic";
  racio_model: string;
  emocio_model: string;
  instinkt_model: string;
  synthesis_model: string;
  use_llm: boolean;
  debug_trace: boolean;
}

export interface SimulateRequest {
  provider: ProviderSelection;
  scenario: {
    title: string;
    prompt: string;
  };
  psyche_state: {
    character_id: CharacterId;
    acceptance_level: number;
    context: ScenarioContext;
    active_triggers?: [];
    facades?: [];
    unmet_goals?: [];
  };
}

export interface SimulateResponse {
  trace: TraceRecord;
  diagnostics: Record<string, unknown>;
}
