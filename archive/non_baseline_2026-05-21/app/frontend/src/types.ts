export type ProfileId =
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

export type MindName = "racio" | "emocio" | "instinkt";
export type MindNameExtended = MindName | "mixed" | "unknown" | "tie";

export interface ProviderSelection {
  provider_mode: "ollama" | "lmstudio" | "deterministic";
  racio_model: string;
  emocio_model: string;
  instinkt_model: string;
  synthesis_model: string;
  use_llm: boolean;
  debug_trace: boolean;
}

export interface PlaygroundStakes {
  financial_risk?: number | null;
  social_exposure?: number | null;
  time_pressure?: number | null;
  relationship_risk?: number | null;
  reversibility?: number | null;
}

export interface PlaygroundScenario {
  title: string;
  situation: string;
  decision_options: string[];
  stakes: PlaygroundStakes;
}

export interface PlaygroundRequest {
  provider: ProviderSelection;
  scenario: PlaygroundScenario;
  profile: ProfileId;
  compare_profiles: ProfileId[];
  user_notes: string;
  acceptance_mode: "unknown" | "accepting" | "mixed" | "conflicted";
  use_memory: boolean;
  save_observation: boolean;
}

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
  known_facts: string[];
  unknowns: string[];
  logical_options: string[];
  timeline_or_sequence: string;
  utility_model: string;
  rationalization_risk: string;
  rationalization_target: string;
  translation_of_other_minds_risk: string;
}

export interface EmocioSignal extends REISignal {
  mind: "emocio";
  current_image: string;
  desired_image: string;
  broken_image: string;
  social_meaning: string;
  attraction_or_rejection: string;
  pride_or_shame: string;
  recognition_need: string;
  body_expression: string;
  attack_impulse: string;
}

export interface InstinktSignal extends REISignal {
  mind: "instinkt";
  threat_map: string;
  loss_map: string;
  fear_feeling: string;
  body_alarm: string;
  trust_boundary: string;
  boundary_issue: string;
  attachment_issue: string;
  scarcity_signal: string;
  flight_or_freeze_signal: string;
  minimum_safety_condition: string;
}

export interface AcceptanceAssessment {
  overall_level: "accepting" | "mixed" | "conflicted" | "unknown";
  racio_acceptance: string;
  emocio_acceptance: string;
  instinkt_acceptance: string;
  main_conflict: string;
  likely_sabotage_point: string;
  task_delegation: Record<string, string>;
  behavioral_alignment: "aligned" | "split" | "ambivalent" | "unknown";
  acceptance_quality: "accepting" | "non_accepting" | "mixed" | "unknown";
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
  perceived_world: string;
  conscious_story: string;
  hidden_signal_sources: Record<string, string>;
  trusted_mind_or_coalition: MindNameExtended;
  suppressed_mind: MindNameExtended;
  final_pressure: string;
  action_tendency: string;
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

export interface OptionEvaluation {
  option: string;
  racio_score: number;
  emocio_score: number;
  instinkt_score: number;
  racio_evaluation: string;
  emocio_evaluation: string;
  instinkt_evaluation: string;
  ego_pressure: string;
  likely_selected_option: string;
  is_likely_selected: boolean;
  rejected_option_reason: string;
}

export interface TrialogueLine {
  processor: MindName;
  label: string;
  caveat: string;
  signal: string;
}

export interface TrialogueRound {
  round: number;
  title: string;
  lines: TrialogueLine[];
}

export interface PlaygroundTrialogue {
  rounds: TrialogueRound[];
  final: {
    perceived_world: string;
    action_tendency: string;
  };
}

export interface ProfileComparison {
  profile: ProfileId;
  canonical_profile: string;
  profile_leader: string;
  situational_driver: string;
  resultant_leader_under_pressure: string;
  selected_option: string;
  perceived_world: string;
  hidden_driver: string;
  smallest_next_step: string;
}

export interface ProcessorRunInstruction {
  processor: "racio" | "emocio" | "instinkt" | "ego" | string;
  label: string;
  model: string;
  system_instruction: string;
  user_payload: string;
  provider_options: Record<string, unknown>;
}

export interface PlaygroundRunResponse {
  safety_framing: string;
  timestamp: string;
  scenario: PlaygroundScenario;
  selected_profile: ProfileId;
  canonical_profile: string;
  options: string[];
  processor_outputs: REICycleResponse;
  option_evaluations: OptionEvaluation[];
  trialogue: PlaygroundTrialogue;
  compare_profiles: ProfileComparison[];
  processor_instructions?: ProcessorRunInstruction[];
  observation_path: string | null;
  user_notes: string;
}

export interface ProviderPayload {
  default: Record<string, unknown>;
  ollama: { available: boolean; models: string[]; recommended: Record<string, string> };
  lmstudio: { available: boolean; models: string[]; recommended: Record<string, string> };
}

export interface RuntimeManifest {
  project: {
    name: string;
    version: string;
    active_stack_id: string;
    active_stack_label: string;
  };
  active_logic?: RuntimeLayerManifest;
  active_motorics?: RuntimeLayerManifest;
  active: {
    engine: RuntimeComponent;
    playground_api: RuntimeComponent & {
      base_path: string;
      endpoints: string[];
      uses_engine_contract: string;
    };
    frontend: RuntimeComponent & {
      api_client_path: string;
      consumes_api_contract: string;
    };
  };
  legacy: RuntimeLegacyComponent[];
  last_verified: Record<string, string>;
}

export interface RuntimeLayerManifest {
  id: string;
  version: string;
  contract_id: string;
  definition: string;
  components: RuntimeLayerComponent[];
  boundaries: string[];
  execution_order?: string[];
}

export interface RuntimeLayerComponent {
  id: string;
  path: string;
  role: string;
  entrypoint?: string;
  schema_version?: string;
}

export interface RuntimeComponent {
  id: string;
  version: string;
  contract_id: string;
  path: string;
  entrypoint?: string;
  notes: string;
}

export interface RuntimeLegacyComponent {
  id: string;
  path: string;
  status: string;
  notes: string;
}

export interface ObservationSummary {
  id: string;
  path: string;
  timestamp: string;
  title: string;
  selected_profile: string;
  selected_option: string;
  user_notes: string;
  safety_framing: string;
}

export type StreamEvent =
  | { event: "status"; data: { message: string; profile?: string; safety_framing?: string } }
  | { event: "processor_instructions"; data: { instructions: ProcessorRunInstruction[] } }
  | { event: "token"; data: { type: string; label?: string; model?: string; content?: string; thinking?: string } }
  | { event: "compare_result"; data: ProfileComparison }
  | { event: "result"; data: PlaygroundRunResponse }
  | { event: "error"; data: { message: string; safety_framing?: string } };
