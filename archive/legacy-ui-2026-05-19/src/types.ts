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

export type MindName = "racio" | "emocio" | "instinkt";
export type MindNameExtended = MindName | "mixed" | "unknown" | "tie";
export type AcceptanceLevel = "accepting" | "mixed" | "conflicted" | "unknown";
export type AcceptanceMode = "unknown" | "accepting" | "mixed" | "conflicted";
export type BehavioralAlignment = "aligned" | "split" | "ambivalent" | "unknown";
export type AcceptanceQuality = "accepting" | "non_accepting" | "mixed" | "unknown";

export interface REISignal {
  mind: MindName;
  is_conscious: boolean;
  translated_by_racio: boolean;
  processing_mode: string;
  perception: string;
  primary_motive: string;
  preferred_action: string;
  accepted_expression: string;
  non_accepted_expression: string;
  resistance_to_other_minds: string;
  what_this_mind_needs: string;
  risk_if_ignored: string;
  risk_if_dominant: string;
  confidence: number;
  uncertainty: string;
  safety_flags: string[];
}

export interface RacioSignal extends REISignal {
  mind: "racio";
  is_conscious: true;
  translated_by_racio: false;
  known_facts: string[];
  unknowns: string[];
  logical_options: string[];
  timeline_or_sequence: string;
  rationalization_risk: string;
}

export interface EmocioSignal extends REISignal {
  mind: "emocio";
  is_conscious: false;
  translated_by_racio: true;
  current_image: string;
  desired_image: string;
  broken_image: string;
  social_meaning: string;
  attraction_or_rejection: string;
  pride_or_shame: string;
  competition_signal: string;
  attack_impulse: string;
}

export interface InstinktSignal extends REISignal {
  mind: "instinkt";
  is_conscious: false;
  translated_by_racio: true;
  threat_map: string;
  loss_map: string;
  body_alarm: string;
  boundary_issue: string;
  trust_issue: string;
  attachment_issue: string;
  scarcity_signal: string;
  flight_or_freeze_signal: string;
  minimum_safety_condition: string;
}

export interface AcceptanceAssessment {
  overall_level: AcceptanceLevel;
  racio_acceptance: string;
  emocio_acceptance: string;
  instinkt_acceptance: string;
  main_conflict: string;
  likely_sabotage_point: string;
  task_delegation: Record<string, string>;
  behavioral_alignment: BehavioralAlignment;
  acceptance_quality: AcceptanceQuality;
  non_acceptance_pattern: string;
  coalition_pattern: string;
  sabotage_mechanism: string;
}

export interface EgoResultant {
  character_profile: string;
  influence_weights: Record<string, number>;
  leading_mind: MindNameExtended;
  resisting_mind: MindNameExtended;
  ignored_or_misrepresented_mind: MindNameExtended;
  profile_leader: MindNameExtended;
  profile_leader_minds: MindName[];
  situational_driver: MindNameExtended;
  resultant_leader_under_pressure: MindNameExtended;
  profile_influence_explanation: string;
  racio_role: "clear_analysis" | "rationalizer" | "overcontroller" | "translator" | "suppressed" | "unknown";
  emocio_role: "motivator" | "image_hunger" | "shame_driver" | "status_driver" | "connector" | "suppressed" | "unknown";
  instinkt_role: "protector" | "freeze_driver" | "boundary_guard" | "panic_driver" | "attachment_guard" | "suppressed" | "unknown";
  decision_stability: "stable" | "fragile" | "unstable" | "unknown";
  profile_sensitivity_note: string;
  conscious_monologue: string;
  hidden_driver: string;
  acceptance_assessment: string;
  main_conflict: string;
  likely_action_under_pressure: string;
  racio_justification_afterwards: string;
  hidden_cost: string;
  integrated_decision: string;
  smallest_acceptable_next_step: string;
  task_delegation: Record<string, string>;
  prediction_if_racio_rules_alone: string;
  prediction_if_emocio_rules_alone: string;
  prediction_if_instinkt_rules_alone: string;
  uncertainty: string;
  safety_flags: string[];
}

export interface REICycleRequest {
  provider: ProviderSelection;
  scenario: {
    title: string;
    prompt: string;
  };
  character_profile: string;
  acceptance_mode: AcceptanceMode;
  rounds: number;
  stream: boolean;
  use_memory: boolean;
}

export interface REICycleResponse {
  mode: "rei_cycle";
  character_profile: string;
  situation: Record<string, string>;
  signals: {
    racio: RacioSignal;
    emocio_translated: EmocioSignal;
    instinkt_translated: InstinktSignal;
  };
  acceptance: AcceptanceAssessment;
  ego_resultant: EgoResultant;
  diagnostics: Record<string, unknown>;
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
