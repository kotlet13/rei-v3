import { BrainCircuit, BriefcaseBusiness, Download, Home, Play, RefreshCw, Server, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { API_BASE, getCharacters, getProviders, runReiCycle, simulate } from "./api";
import type {
  CharacterDefinition,
  CharacterId,
  MindId,
  ProviderSelection,
  REICycleResponse,
  SimulateRequest,
  TraceRecord,
} from "./types";

const DEFAULT_SCENARIO =
  "A person has to step in front of a full auditorium in five minutes. On the outside they look calm, but inside they feel the performance could reveal a crack in their image of competence.";

const mindNames: Record<MindId, string> = {
  R: "Racio",
  E: "Emocio",
  I: "Instinkt",
};

const mindClass: Record<MindId, string> = {
  R: "mind-r",
  E: "mind-e",
  I: "mind-i",
};

const defaultProvider: ProviderSelection = {
  provider_mode: "lmstudio",
  racio_model: "qwen/qwen3.5-9b",
  emocio_model: "qwen/qwen3.5-9b",
  instinkt_model: "qwen/qwen3.5-9b",
  synthesis_model: "qwen/qwen3.5-9b",
  use_llm: true,
  debug_trace: true,
};

const HISTORY_STORAGE_KEY = "rei.runHistory.v1";
const CYCLE_FEEDBACK_STORAGE_KEY = "rei.cycleFeedback.v1";
const MAX_HISTORY_ITEMS = 40;

interface ScenarioPreset {
  id: string;
  label: string;
  Icon: typeof BriefcaseBusiness;
  title: string;
  prompt: string;
  characterId: CharacterId;
  acceptance: number;
  setting: string;
  socialExposure: number;
  timePressure: number;
  relationshipStake: number;
  bodilyState: string;
}

interface RunHistoryItem {
  id: string;
  createdAt: string;
  title: string;
  characterId: CharacterId;
  chosenOption: string;
  summary: string;
  trace: TraceRecord;
  diagnostics: Record<string, unknown> | null;
}

interface SimpleRunResult {
  character: CharacterDefinition;
  trace: TraceRecord;
  diagnostics: Record<string, unknown> | null;
}

interface CycleFeedback {
  accuracy: string;
  novelty: string;
  plausible: string;
  wrong: string;
}

type CycleSignal = REICycleResponse["signals"][keyof REICycleResponse["signals"]];

const scenarioPresets: ScenarioPreset[] = [
  {
    id: "career",
    label: "Career",
    Icon: BriefcaseBusiness,
    title: "Career path under family pressure",
    prompt:
      "A person must choose exactly one concrete career path from this list: software engineer, UX designer, cybersecurity analyst, clinical psychologist, brand strategist, teacher, emergency nurse, lawyer, product manager, or performer. Their family expects a practical and respected profession. They feel drawn toward visible creative work, but they also fear instability, failure, and disappointing people who depend on them. The final synthesis must name exactly one listed profession in the first sentence and must not invent a hybrid.",
    characterId: "REI",
    acceptance: 0.35,
    setting: "family discussion about career choice",
    socialExposure: 0.55,
    timePressure: 0.65,
    relationshipStake: 0.75,
    bodilyState: "tight chest, alert posture, restless focus",
  },
  {
    id: "lifestyle",
    label: "Lifestyle",
    Icon: Home,
    title: "Choosing a way of life",
    prompt:
      "A person has to choose one concrete way of life: a fast urban life with career momentum, a quieter home-centered life with fewer risks, or a more nomadic path with freedom and uncertainty. Each option promises something real and takes something away. The final synthesis must name exactly one lifestyle in the first sentence.",
    characterId: "RI",
    acceptance: 0.46,
    setting: "late evening alone with apartment listings, budgets, and travel plans",
    socialExposure: 0.34,
    timePressure: 0.52,
    relationshipStake: 0.58,
    bodilyState: "tired body, scattered attention, low background anxiety",
  },
  {
    id: "fantasy-character",
    label: "Fantasy Character",
    Icon: Sparkles,
    title: "Fantasy character identity",
    prompt:
      "A person imagines what kind of fantasy character they would become in a dangerous kingdom: a strategist, a healer, a performer, a guardian, a spy, a ruler, or a wanderer. They want one concrete role that feels alive, useful, and survivable. The final synthesis must name exactly one fantasy role in the first sentence.",
    characterId: "E>I>R",
    acceptance: 0.40,
    setting: "imagined fantasy kingdom at the edge of conflict",
    socialExposure: 0.72,
    timePressure: 0.44,
    relationshipStake: 0.64,
    bodilyState: "excited pulse, vivid images, cautious tension",
  },
];

export default function App() {
  const [characters, setCharacters] = useState<CharacterDefinition[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [providerStatus, setProviderStatus] = useState({ ollama: false, lmstudio: false });
  const [provider, setProvider] = useState<ProviderSelection>(defaultProvider);
  const [simpleMode, setSimpleMode] = useState(true);
  const [reiCycleMode, setReiCycleMode] = useState(false);
  const [title, setTitle] = useState("Public speaking and stage fright");
  const [prompt, setPrompt] = useState(DEFAULT_SCENARIO);
  const [characterId, setCharacterId] = useState<CharacterId>("REI");
  const [acceptance, setAcceptance] = useState(0.34);
  const [setting, setSetting] = useState("stage in front of a full auditorium");
  const [socialExposure, setSocialExposure] = useState(0.94);
  const [timePressure, setTimePressure] = useState(0.72);
  const [relationshipStake, setRelationshipStake] = useState(0.44);
  const [bodilyState, setBodilyState] = useState("elevated heart rate and tense posture");
  const [trace, setTrace] = useState<TraceRecord | null>(null);
  const [cycleResponse, setCycleResponse] = useState<REICycleResponse | null>(null);
  const [cycleFeedback, setCycleFeedback] = useState<CycleFeedback>(readStoredCycleFeedback);
  const [diagnostics, setDiagnostics] = useState<Record<string, unknown> | null>(null);
  const [simpleRuns, setSimpleRuns] = useState<SimpleRunResult[]>([]);
  const [history, setHistory] = useState<RunHistoryItem[]>(readStoredHistory);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([getCharacters(), getProviders()])
      .then(([characterPayload, providerPayload]) => {
        setCharacters(characterPayload);
        setModels(Array.from(new Set([...providerPayload.lmstudio.models, ...providerPayload.ollama.models])));
        setProviderStatus({
          ollama: providerPayload.ollama.available,
          lmstudio: providerPayload.lmstudio.available,
        });
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history.slice(0, MAX_HISTORY_ITEMS)));
    } catch {
      // History is a convenience layer. A full storage bucket should not block a simulation.
    }
  }, [history]);

  useEffect(() => {
    try {
      localStorage.setItem(CYCLE_FEEDBACK_STORAGE_KEY, JSON.stringify(cycleFeedback));
    } catch {
      // Local feedback should never block a simulation.
    }
  }, [cycleFeedback]);

  const selectedCharacter = useMemo(
    () => characters.find((character) => character.id === characterId),
    [characters, characterId],
  );

  async function runSimulation() {
    setLoading(true);
    setError(null);
    try {
      if (reiCycleMode) {
        const response = await runReiCycle({
          provider,
          scenario: { title, prompt },
          character_profile: characterId,
          acceptance_mode: "unknown",
          rounds: 0,
          stream: false,
          use_memory: true,
        });
        setCycleResponse(response);
        setDiagnostics(response.diagnostics);
        setTrace(null);
        setSimpleRuns([]);
        setSelectedHistoryId(null);
        return;
      }

      if (simpleMode) {
        if (!characters.length) {
          throw new Error("Characters are not loaded yet.");
        }
        const lowContextScenario = buildLowContextScenario(title, prompt);
        const results: SimpleRunResult[] = [];
        setCycleResponse(null);
        setTrace(null);
        setDiagnostics(null);
        setSimpleRuns([]);
        setSelectedHistoryId(null);

        for (const character of characters) {
          const payload: SimulateRequest = {
            provider,
            scenario: lowContextScenario,
            psyche_state: {
              character_id: character.id,
              acceptance_level: acceptance,
              active_triggers: [],
              facades: [],
              unmet_goals: [],
              context: {
                setting,
                social_exposure: socialExposure,
                time_pressure: timePressure,
                relationship_stake: relationshipStake,
                bodily_state: bodilyState || undefined,
              },
            },
          };
          const response = await simulate(payload);
          results.push({ character, trace: response.trace, diagnostics: response.diagnostics });
          setSimpleRuns([...results]);
        }
        return;
      }

      const payload: SimulateRequest = {
        provider,
        scenario: { title, prompt },
        psyche_state: {
          character_id: characterId,
          acceptance_level: acceptance,
          active_triggers: [],
          facades: [],
          unmet_goals: [],
          context: {
            setting,
            social_exposure: socialExposure,
            time_pressure: timePressure,
            relationship_stake: relationshipStake,
            bodily_state: bodilyState || undefined,
          },
        },
      };
      const response = await simulate(payload);
      const historyItem = buildHistoryItem(response.trace, response.diagnostics);
      setCycleResponse(null);
      setTrace(response.trace);
      setDiagnostics(response.diagnostics);
      setSimpleRuns([]);
      setSelectedHistoryId(historyItem.id);
      setHistory((previous) => [
        historyItem,
        ...previous.filter((item) => item.id !== historyItem.id),
      ].slice(0, MAX_HISTORY_ITEMS));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  function exportRun() {
    if (!trace && !cycleResponse) return;
    const exportPayload = cycleResponse ? { cycleResponse, diagnostics } : { trace, diagnostics };
    const blob = new Blob([JSON.stringify(exportPayload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = cycleResponse ? "rei-cycle-run.json" : `${trace?.trace_id ?? "rei"}-run.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function updateProvider<K extends keyof ProviderSelection>(key: K, value: ProviderSelection[K]) {
    setProvider((previous) => ({ ...previous, [key]: value }));
  }

  function applyPreset(preset: ScenarioPreset) {
    setTitle(preset.title);
    setPrompt(preset.prompt);
    setCharacterId(preset.characterId);
    setAcceptance(preset.acceptance);
    setSetting(preset.setting);
    setSocialExposure(preset.socialExposure);
    setTimePressure(preset.timePressure);
    setRelationshipStake(preset.relationshipStake);
    setBodilyState(preset.bodilyState);
    setCycleResponse(null);
    setTrace(null);
    setDiagnostics(null);
    setSimpleRuns([]);
    setError(null);
  }

  function openHistoryItem(item: RunHistoryItem) {
    setCycleResponse(null);
    setTrace(item.trace);
    setDiagnostics(item.diagnostics);
    setSimpleRuns([]);
    setSelectedHistoryId(item.id);
    setError(null);
  }

  function clearHistory() {
    setHistory([]);
    setSelectedHistoryId(null);
  }

  function updateCycleFeedback<K extends keyof CycleFeedback>(key: K, value: CycleFeedback[K]) {
    setCycleFeedback((previous) => ({ ...previous, [key]: value }));
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">REI v3 PoC</p>
          <h1>Inner Monologue Simulator</h1>
        </div>
        <div className="status-strip">
          <span className={providerStatus.lmstudio ? "status ok" : "status warn"}>
            <Server size={16} aria-hidden="true" />
            LM Studio {providerStatus.lmstudio ? "available" : "unavailable"}
          </span>
          <span className={providerStatus.ollama ? "status ok" : "status warn"}>
            <Server size={16} aria-hidden="true" />
            Ollama {providerStatus.ollama ? "available" : "unavailable"}
          </span>
          <span className="status">
            <ShieldCheck size={16} aria-hidden="true" />
            {API_BASE}
          </span>
        </div>
      </header>

      <section className="workspace-grid">
        <form className="panel input-panel" onSubmit={(event) => void event.preventDefault()}>
          <div className="panel-header">
            <h2>Scenario</h2>
            <div className="action-row">
              <label className="switch">
                <input
                  type="checkbox"
                  checked={simpleMode}
                  onChange={(event) => {
                    setSimpleMode(event.target.checked);
                    if (event.target.checked) setReiCycleMode(false);
                    setCycleResponse(null);
                    setTrace(null);
                    setDiagnostics(null);
                    setSimpleRuns([]);
                  }}
                />
                <span>Simple</span>
              </label>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={reiCycleMode}
                  onChange={(event) => {
                    setReiCycleMode(event.target.checked);
                    if (event.target.checked) setSimpleMode(false);
                    setCycleResponse(null);
                    setTrace(null);
                    setDiagnostics(null);
                    setSimpleRuns([]);
                  }}
                />
                <span>Cycle</span>
              </label>
              <button
                className="primary-button"
                type="button"
                onClick={runSimulation}
                disabled={loading || (simpleMode && !characters.length)}
              >
                {loading ? <RefreshCw className="spin" size={18} /> : <Play size={18} />}
                {loading ? "Simulating" : reiCycleMode ? "Run cycle" : simpleMode ? "Run all" : "Simulate"}
              </button>
            </div>
          </div>

          <div className="preset-grid" aria-label="Scenario presets">
            {scenarioPresets.map((preset) => {
              const Icon = preset.Icon;
              return (
                <button className="preset-button" type="button" key={preset.id} onClick={() => applyPreset(preset)}>
                  <Icon size={17} aria-hidden="true" />
                  {preset.label}
                </button>
              );
            })}
          </div>

          {!simpleMode && (
            <label>
              Title
              <input value={title} onChange={(event) => setTitle(event.target.value)} />
            </label>
          )}

          <label>
            Input scenario
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={simpleMode ? 5 : 8} />
          </label>

          {simpleMode ? (
            <div className="simple-controls">
              <Slider
                label="Acceptance"
                value={acceptance}
                onChange={setAcceptance}
                low="low"
                high="high"
              />
            </div>
          ) : (
            <>
              <div className="two-col">
                <label>
                  Character
                  <select value={characterId} onChange={(event) => setCharacterId(event.target.value as CharacterId)}>
                    {characters.map((character) => (
                      <option key={character.id} value={character.id}>
                        {character.id} - {character.hierarchy}
                      </option>
                    ))}
                  </select>
                </label>
                <Slider
                  label="Acceptance"
                  value={acceptance}
                  onChange={setAcceptance}
                  low="low"
                  high="high"
                />
              </div>

              {selectedCharacter && (
                <div className="character-note">
                  <strong>{selectedCharacter.hierarchy}</strong>
                  <span>{selectedCharacter.description}</span>
                </div>
              )}

              <div className="context-grid">
                <label>
                  Setting
                  <input value={setting} onChange={(event) => setSetting(event.target.value)} />
                </label>
                <label>
                  Body state
                  <input value={bodilyState} onChange={(event) => setBodilyState(event.target.value)} />
                </label>
                <Slider label="Public exposure" value={socialExposure} onChange={setSocialExposure} />
                <Slider label="Time pressure" value={timePressure} onChange={setTimePressure} />
                <Slider label="Relationship stake" value={relationshipStake} onChange={setRelationshipStake} />
              </div>
            </>
          )}
        </form>

        <aside className="panel provider-panel">
          <div className="panel-header compact">
            <h2>Models</h2>
            <div className="switch-row">
              <label className="switch">
                <input
                  type="checkbox"
                  checked={provider.use_llm}
                  onChange={(event) => updateProvider("use_llm", event.target.checked)}
                />
                <span>LLM</span>
              </label>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={provider.debug_trace}
                  onChange={(event) => updateProvider("debug_trace", event.target.checked)}
                />
                <span>Debug</span>
              </label>
            </div>
          </div>
          <label>
            Mode
            <select
              value={provider.provider_mode}
              onChange={(event) =>
                updateProvider("provider_mode", event.target.value as ProviderSelection["provider_mode"])
              }
            >
              <option value="ollama">Ollama</option>
              <option value="lmstudio">LM Studio</option>
              <option value="deterministic">Deterministic</option>
            </select>
          </label>
          <ModelSelect label="Racio" value={provider.racio_model} models={models} onChange={(value) => updateProvider("racio_model", value)} />
          <ModelSelect label="Emocio" value={provider.emocio_model} models={models} onChange={(value) => updateProvider("emocio_model", value)} />
          <ModelSelect label="Instinkt" value={provider.instinkt_model} models={models} onChange={(value) => updateProvider("instinkt_model", value)} />
          <ModelSelect label="Synthesis" value={provider.synthesis_model} models={models} onChange={(value) => updateProvider("synthesis_model", value)} />
          <section className="history-panel" aria-label="Decision history">
            <div className="history-header">
              <h2>History</h2>
              <button className="text-button" type="button" onClick={clearHistory} disabled={!history.length}>
                Clear
              </button>
            </div>
            {history.length ? (
              <div className="history-list">
                {history.map((item) => (
                  <button
                    className={`history-item ${item.id === selectedHistoryId ? "active" : ""}`}
                    type="button"
                    key={item.id}
                    onClick={() => openHistoryItem(item)}
                  >
                    <span>{item.chosenOption}</span>
                    <small>
                      {item.characterId} · {item.title} · {formatHistoryDate(item.createdAt)}
                    </small>
                  </button>
                ))}
              </div>
            ) : (
              <p className="empty-history">Final decisions will appear here after a run.</p>
            )}
          </section>
          {error && <div className="error-box">{error}</div>}
          {diagnostics && (
            <details className="diagnostics">
              <summary>Diagnostics</summary>
              <pre>{JSON.stringify(diagnostics, null, 2)}</pre>
            </details>
          )}
        </aside>
      </section>

      {simpleRuns.length > 0 && (
        <section className="simple-results panel" aria-label="All character decisions">
          <div className="panel-header compact">
            <h2>All Character Decisions</h2>
            <span>{simpleRuns.length} runs</span>
          </div>
          <div className="simple-result-grid">
            {simpleRuns.map(({ character, trace: runTrace }) => (
              <article className="simple-result-card" key={character.id}>
                <header>
                  <span>{character.id}</span>
                  <div>
                    <h3>{character.hierarchy}</h3>
                    <strong>{decisionLabel(runTrace)}</strong>
                  </div>
                </header>
                <p className="simple-final">{runTrace.synthesis_turn.final_monologue}</p>
                <div className="simple-lines">
                  {runTrace.mind_turns.map((turn) => (
                    <p className={mindClass[turn.mind_id]} key={turn.mind_id}>
                      <span>{turn.mind_id}</span>
                      {turn.inner_line}
                    </p>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {cycleResponse && (
        <section className="result-grid cycle-result-grid" aria-label="Inner monologue cycle">
          <section className="panel cycle-drivers-panel">
            <div className="panel-header">
              <h2>Inner Monologue Cycle</h2>
              <button className="secondary-button" type="button" onClick={exportRun}>
                <Download size={18} />
                Export run
              </button>
            </div>
            <div className="driver-list">
              <Field label="Profile" value={cycleResponse.character_profile} />
              <Field label="Profile leader" value={cycleResponse.ego_resultant.profile_leader} />
              <Field label="Profile leader minds" value={cycleResponse.ego_resultant.profile_leader_minds} />
              <Field label="Situational driver" value={cycleResponse.ego_resultant.situational_driver} />
              <Field label="Resultant under pressure" value={cycleResponse.ego_resultant.resultant_leader_under_pressure} />
              <Field label="Racio role" value={cycleResponse.ego_resultant.racio_role} />
              <Field label="Emocio role" value={cycleResponse.ego_resultant.emocio_role} />
              <Field label="Instinkt role" value={cycleResponse.ego_resultant.instinkt_role} />
              <Field label="Decision stability" value={cycleResponse.ego_resultant.decision_stability} />
              <Field label="Profile influence" value={cycleResponse.ego_resultant.profile_influence_explanation} />
            </div>
          </section>

          <section className="panel cycle-acceptance-panel">
            <h2>Acceptance / Non-acceptance</h2>
            <div className="driver-list">
              <Field label="Overall level" value={cycleResponse.acceptance.overall_level} />
              <Field label="Behavioral alignment" value={cycleResponse.acceptance.behavioral_alignment} />
              <Field label="Acceptance quality" value={cycleResponse.acceptance.acceptance_quality} />
              <Field label="Non-acceptance pattern" value={cycleResponse.acceptance.non_acceptance_pattern} />
              <Field label="Coalition pattern" value={cycleResponse.acceptance.coalition_pattern} />
              <Field label="Sabotage mechanism" value={cycleResponse.acceptance.sabotage_mechanism} />
              <Field label="Main conflict" value={cycleResponse.acceptance.main_conflict} />
              <Field label="Task delegation" value={cycleResponse.acceptance.task_delegation} />
            </div>
          </section>

          <section className="panel cycle-prediction-panel">
            <div className="panel-header compact">
              <h2>Ego Resultant</h2>
              <BrainCircuit size={20} aria-hidden="true" />
            </div>
            <p className="final-monologue">{cycleResponse.ego_resultant.likely_action_under_pressure}</p>
            <div className="integration-grid">
              <Field label="Racio justification afterward" value={cycleResponse.ego_resultant.racio_justification_afterwards} />
              <Field label="Hidden driver" value={cycleResponse.ego_resultant.hidden_driver} />
              <Field label="Hidden cost" value={cycleResponse.ego_resultant.hidden_cost} />
              <Field label="Integrated decision" value={cycleResponse.ego_resultant.integrated_decision} />
              <Field label="Smallest acceptable next step" value={cycleResponse.ego_resultant.smallest_acceptable_next_step} />
              <Field label="Uncertainty" value={cycleResponse.ego_resultant.uncertainty} />
            </div>
          </section>
        </section>
      )}

      {cycleResponse && (
        <section className="voices-grid" aria-label="REI cycle processor signals">
          <CycleSignalCard title="Conscious Racio Monologue" signal={cycleResponse.signals.racio} />
          <CycleSignalCard title="Translated Emocio Signal" signal={cycleResponse.signals.emocio_translated} />
          <CycleSignalCard title="Translated Instinkt Signal" signal={cycleResponse.signals.instinkt_translated} />
        </section>
      )}

      {cycleResponse && (
        <section className="panel cycle-feedback-panel" aria-label="Cycle feedback">
          <div className="panel-header compact">
            <h2>Feedback</h2>
            <span>local</span>
          </div>
          <div className="feedback-grid">
            <RatingSelect label="Accuracy" value={cycleFeedback.accuracy} onChange={(value) => updateCycleFeedback("accuracy", value)} />
            <RatingSelect label="New signal" value={cycleFeedback.novelty} onChange={(value) => updateCycleFeedback("novelty", value)} />
            <RatingSelect label="Prediction" value={cycleFeedback.plausible} onChange={(value) => updateCycleFeedback("plausible", value)} />
            <label className="feedback-text">
              Wrong
              <textarea value={cycleFeedback.wrong} onChange={(event) => updateCycleFeedback("wrong", event.target.value)} rows={3} />
            </label>
          </div>
        </section>
      )}

      {trace && (
        <section className="result-grid">
          <section className="panel">
            <div className="panel-header">
              <h2>Deviation and Correction</h2>
              <button className="secondary-button" type="button" onClick={exportRun}>
                <Download size={18} />
                Export run
              </button>
            </div>
            <MetricBar label="Fear closure" value={trace.psyche_state.deviation_state?.fear_closure ?? 0} />
            <MetricBar label="Image projection" value={trace.psyche_state.deviation_state?.image_projection ?? 0} />
            <MetricBar label="Abstract detachment" value={trace.psyche_state.deviation_state?.abstract_detachment ?? 0} />
            <div className="correction-note">
              <span>Dominant edge</span>
              <strong>{trace.psyche_state.corrective_cycle?.dominant_edge ?? "none"}</strong>
              <p>{trace.psyche_state.corrective_cycle?.note}</p>
            </div>
          </section>

          <section className="panel">
            <h2>Conflict and Coalition</h2>
            <div className="matrix">
              {Object.entries(trace.psyche_state.pairwise_conflict ?? {}).map(([key, value]) => (
                <div className={`matrix-cell ${conflictClass(value)}`} key={key}>
                  <span>{key}</span>
                  <strong>{value.toFixed(2)}</strong>
                </div>
              ))}
            </div>
            <div className="decision">
              <span>Winning coalition</span>
              <strong>{trace.synthesis_turn.dominant_coalition.join(" + ")}</strong>
              <span>Blocked processor</span>
              <strong>{trace.synthesis_turn.blocked_mind ?? "none"}</strong>
              <span>Rule</span>
              <p>{trace.synthesis_turn.decision_rule}</p>
            </div>
          </section>

          {trace.synthesis_turn.decision && (
            <section className="panel decision-mode-panel">
              <h2>Decision Mode</h2>
              <div className="chosen-decision">
                <span>Chosen option</span>
                <strong>{trace.synthesis_turn.decision.chosen_option}</strong>
                <small>confidence {trace.synthesis_turn.decision.confidence.toFixed(2)}</small>
              </div>
              <div className="vote-grid">
                {trace.synthesis_turn.decision.mind_votes.map((vote) => (
                  <div className={`vote-card ${mindClass[vote.mind_id]}`} key={vote.mind_id}>
                    <span>{vote.mind_id}</span>
                    <strong>{vote.chosen_option}</strong>
                    <small>{vote.score.toFixed(2)}</small>
                  </div>
                ))}
              </div>
              <div className="ranking-list">
                {trace.synthesis_turn.decision.ranking.slice(0, 5).map((item) => (
                  <div key={item.option}>
                    <span>{item.option}</span>
                    <strong>{item.score.toFixed(2)}</strong>
                  </div>
                ))}
              </div>
              <p className="decision-rationale">{trace.synthesis_turn.decision.rationale}</p>
            </section>
          )}

          <section className="panel synthesis-panel">
            <h2>Final Synthesis</h2>
            <p className="final-monologue">{trace.synthesis_turn.final_monologue}</p>
            <p className="correction-copy">{trace.synthesis_turn.correction_explanation}</p>
            <div className="integration-grid">
              <Field label="Agreement" value={trace.synthesis_turn.main_agreement} />
              <Field label="Conflict" value={trace.synthesis_turn.main_conflict} />
              <Field label="Hidden driver" value={trace.synthesis_turn.possible_hidden_driver} />
              <Field label="Reversible next step" value={trace.synthesis_turn.smallest_reversible_next_step} />
              <Field label="Spoznanje marker" value={trace.synthesis_turn.what_would_count_as_spoznanje} />
              <Field label="Uncertainty" value={trace.synthesis_turn.uncertainty} />
            </div>
            <ListField label="Safety flags" values={trace.synthesis_turn.safety_or_ethics_flags ?? []} />
            <div className="tag-row">
              {trace.synthesis_turn.risk_tags.length ? (
                trace.synthesis_turn.risk_tags.map((tag) => <span key={tag}>{tag}</span>)
              ) : (
                <span>no risk flagged</span>
              )}
            </div>
          </section>
        </section>
      )}

      {trace && (
        <section className="panel conversation-flow" aria-label="Conversation flow">
          <div className="panel-header compact">
            <h2>Conversation Flow</h2>
            <span>{trace.scenario.title}</span>
          </div>
          <div className="flow-list">
            {trace.mind_turns.map((turn) => (
              <article className={`flow-item ${mindClass[turn.mind_id]}`} key={turn.mind_id}>
                <span>{turn.mind_id}</span>
                <div>
                  <strong>{mindNames[turn.mind_id]}</strong>
                  <p>{turn.inner_line}</p>
                  <small>{turn.main_concern || turn.proposed_action}</small>
                </div>
              </article>
            ))}
            <article className="flow-item synthesis">
              <span>S</span>
              <div>
                <strong>Synthesis</strong>
                <p>{trace.synthesis_turn.final_monologue}</p>
                <small>{trace.synthesis_turn.decision?.chosen_option ?? summarizeText(trace.synthesis_turn.final_monologue)}</small>
              </div>
            </article>
          </div>
        </section>
      )}

      {trace && (
        <section className="voices-grid" aria-label="R E I processor signals">
          {trace.mind_turns.map((turn) => (
            <article className={`voice-card ${mindClass[turn.mind_id]}`} key={turn.mind_id}>
              <div className="voice-head">
                <span>{turn.mind_id}</span>
                <div>
                  <h3>{mindNames[turn.mind_id]}</h3>
                  <p>intensity {turn.intensity.toFixed(2)} / confidence {(turn.confidence ?? turn.intensity).toFixed(2)}</p>
                </div>
              </div>
              <Field label="Signal type" value={turn.native_signal_type} />
              <Field label="Perception" value={turn.perception} />
              <Field label="Interpretation" value={turn.interpretation} />
              <Field label="Goal" value={turn.goal} />
              <Field label="Fear / desire" value={turn.fear_or_desire} />
              <Field label="Proposal" value={turn.proposed_action} />
              <Field label="Main concern" value={turn.main_concern} />
              <Field label="May be missing" value={turn.what_this_mind_may_be_missing} />
              <Field label="Risk if ignored" value={turn.risk_if_ignored} />
              <Field label="Risk if overpowered" value={turn.risk_if_overpowered} />
              <Field label="Needs" value={turn.needs_from_other_minds} />
              <ListField label="Missing info" values={turn.missing_information ?? []} />
              <blockquote>{turn.inner_line}</blockquote>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}

function CycleSignalCard({ title, signal }: { title: string; signal: CycleSignal }) {
  return (
    <article className={`voice-card ${cycleMindClass(signal.mind)}`}>
      <div className="voice-head">
        <span>{signal.mind[0].toUpperCase()}</span>
        <div>
          <h3>{title}</h3>
          <p>
            {signal.translated_by_racio ? "translated" : "conscious"} / confidence {signal.confidence.toFixed(2)}
          </p>
        </div>
      </div>
      <Field label="Processing mode" value={signal.processing_mode} />
      <Field label="Perception" value={signal.perception} />
      <Field label="Primary motive" value={signal.primary_motive} />
      <Field label="Preferred action" value={signal.preferred_action} />
      <Field label="Accepted expression" value={signal.accepted_expression} />
      <Field label="Non-accepted expression" value={signal.non_accepted_expression} />
      <Field label="Resistance" value={signal.resistance_to_other_minds} />
      <Field label="Needs" value={signal.what_this_mind_needs} />
      <Field label="Risk if ignored" value={signal.risk_if_ignored} />
      <Field label="Risk if dominant" value={signal.risk_if_dominant} />
      {signal.mind === "racio" && (
        <>
          <ListField label="Known facts" values={signal.known_facts} />
          <ListField label="Unknowns" values={signal.unknowns} />
          <ListField label="Options" values={signal.logical_options} />
          <Field label="Sequence" value={signal.timeline_or_sequence} />
          <Field label="Rationalization risk" value={signal.rationalization_risk} />
        </>
      )}
      {signal.mind === "emocio" && (
        <>
          <Field label="Current image" value={signal.current_image} />
          <Field label="Desired image" value={signal.desired_image} />
          <Field label="Broken image" value={signal.broken_image} />
          <Field label="Social meaning" value={signal.social_meaning} />
          <Field label="Pride / shame" value={signal.pride_or_shame} />
          <Field label="Attack impulse" value={signal.attack_impulse} />
        </>
      )}
      {signal.mind === "instinkt" && (
        <>
          <Field label="Threat map" value={signal.threat_map} />
          <Field label="Loss map" value={signal.loss_map} />
          <Field label="Body alarm" value={signal.body_alarm} />
          <Field label="Boundary issue" value={signal.boundary_issue} />
          <Field label="Attachment issue" value={signal.attachment_issue} />
          <Field label="Minimum safety" value={signal.minimum_safety_condition} />
        </>
      )}
      <Field label="Uncertainty" value={signal.uncertainty} />
      <ListField label="Safety flags" values={signal.safety_flags} />
    </article>
  );
}

function buildHistoryItem(trace: TraceRecord, diagnostics: Record<string, unknown> | null): RunHistoryItem {
  return {
    id: trace.trace_id,
    createdAt: trace.created_at,
    title: trace.scenario.title,
    characterId: trace.psyche_state.character_id,
    chosenOption: trace.synthesis_turn.decision?.chosen_option ?? summarizeText(trace.synthesis_turn.final_monologue),
    summary: summarizeText(trace.synthesis_turn.final_monologue),
    trace,
    diagnostics,
  };
}

function buildLowContextScenario(title: string, prompt: string): { title: string; prompt: string } {
  const input = prompt.trim() || title.trim() || "Choose one concrete path.";
  const normalized = input.toLowerCase();
  const trimmedTitle = title.trim();
  const careerPreset = scenarioPresets.find((preset) => preset.id === "career");
  const lifestylePreset = scenarioPresets.find((preset) => preset.id === "lifestyle");
  const fantasyPreset = scenarioPresets.find((preset) => preset.id === "fantasy-character");
  const exactPreset = scenarioPresets.find((preset) => preset.title === trimmedTitle || preset.prompt === input);

  if (exactPreset) {
    return { title: exactPreset.title, prompt: exactPreset.prompt };
  }

  if (lifestylePreset && /\b(lifestyle|way of life|life path|urban|home|nomadic)\b/.test(normalized)) {
    return { title: lifestylePreset.title, prompt: lifestylePreset.prompt };
  }
  if (fantasyPreset && /\b(fantasy|character|kingdom|role)\b/.test(normalized)) {
    return { title: fantasyPreset.title, prompt: fantasyPreset.prompt };
  }
  if (careerPreset && /\b(career|profession|job|work)\b/.test(normalized)) {
    return { title: careerPreset.title, prompt: careerPreset.prompt };
  }

  return {
    title: title.trim() || "Low-context decision",
    prompt: `${input} Choose exactly one concrete answer. The final synthesis must name one concrete choice in the first sentence.`,
  };
}

function decisionLabel(trace: TraceRecord) {
  return trace.synthesis_turn.decision?.chosen_option ?? summarizeText(trace.synthesis_turn.final_monologue);
}

function readStoredHistory(): RunHistoryItem[] {
  try {
    const storedHistory = localStorage.getItem(HISTORY_STORAGE_KEY);
    if (!storedHistory) return [];
    const parsed = JSON.parse(storedHistory) as RunHistoryItem[];
    return Array.isArray(parsed) ? parsed.slice(0, MAX_HISTORY_ITEMS) : [];
  } catch {
    localStorage.removeItem(HISTORY_STORAGE_KEY);
    return [];
  }
}

function readStoredCycleFeedback(): CycleFeedback {
  try {
    const storedFeedback = localStorage.getItem(CYCLE_FEEDBACK_STORAGE_KEY);
    if (!storedFeedback) return { accuracy: "", novelty: "", plausible: "", wrong: "" };
    const parsed = JSON.parse(storedFeedback) as Partial<CycleFeedback>;
    return {
      accuracy: parsed.accuracy ?? "",
      novelty: parsed.novelty ?? "",
      plausible: parsed.plausible ?? "",
      wrong: parsed.wrong ?? "",
    };
  } catch {
    localStorage.removeItem(CYCLE_FEEDBACK_STORAGE_KEY);
    return { accuracy: "", novelty: "", plausible: "", wrong: "" };
  }
}

function cycleMindClass(mind: string) {
  if (mind === "racio") return "mind-r";
  if (mind === "emocio") return "mind-e";
  return "mind-i";
}

function summarizeText(text: string) {
  const normalized = text.trim().replace(/\s+/g, " ");
  const sentence = normalized.split(/(?<=[.!?])\s+/)[0] ?? normalized;
  return sentence.length > 96 ? `${sentence.slice(0, 93)}...` : sentence;
}

function formatHistoryDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function Slider({
  label,
  value,
  onChange,
  low = "0",
  high = "1",
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  low?: string;
  high?: string;
}) {
  return (
    <label className="slider-label">
      <span>
        {label}
        <strong>{value.toFixed(2)}</strong>
      </span>
      <input
        type="range"
        min="0"
        max="1"
        step="0.01"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <small>
        <span>{low}</span>
        <span>{high}</span>
      </small>
    </label>
  );
}

function ModelSelect({
  label,
  value,
  models,
  onChange,
}: {
  label: string;
  value: string;
  models: string[];
  onChange: (value: string) => void;
}) {
  const options = models.includes(value) ? models : [value, ...models];
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((model) => (
          <option key={model} value={model}>
            {model}
          </option>
        ))}
      </select>
    </label>
  );
}

function RatingSelect({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">-</option>
        {[1, 2, 3, 4, 5].map((rating) => (
          <option key={rating} value={String(rating)}>
            {rating}
          </option>
        ))}
      </select>
    </label>
  );
}

function MetricBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <div>
        <span>{label}</span>
        <strong>{value.toFixed(2)}</strong>
      </div>
      <div className="bar">
        <i style={{ width: `${Math.max(2, Math.round(value * 100))}%` }} />
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value?: unknown }) {
  if (value === null || value === undefined || value === "") return null;
  const rendered = Array.isArray(value)
    ? value.join("; ")
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);
  if (!rendered) return null;
  return (
    <div className="voice-field">
      <span>{label}</span>
      <p>{rendered}</p>
    </div>
  );
}

function ListField({ label, values }: { label: string; values?: string[] | null }) {
  const cleanValues = (values ?? []).filter(Boolean);
  if (!cleanValues.length) return null;
  return (
    <div className="voice-field list-field">
      <span>{label}</span>
      <ul>
        {cleanValues.map((value) => (
          <li key={value}>{value}</li>
        ))}
      </ul>
    </div>
  );
}

function conflictClass(value: number) {
  if (value < 0.34) return "low";
  if (value < 0.67) return "medium";
  return "high";
}
