import {
  BrainCircuit,
  CheckCircle2,
  History,
  ListChecks,
  MessageSquareText,
  Play,
  RefreshCw,
  Save,
  Server,
  ShieldCheck,
  SlidersHorizontal,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  API_BASE,
  getObservation,
  getObservations,
  getProfiles,
  getProviders,
  getRuntimeManifest,
  streamPlayground,
} from "./api";
import type {
  EmocioSignal,
  InstinktSignal,
  ObservationSummary,
  PlaygroundRequest,
  PlaygroundRunResponse,
  PlaygroundStakes,
  ProcessorRunInstruction,
  ProfileId,
  ProviderSelection,
  RacioSignal,
  RuntimeManifest,
  StreamEvent,
} from "./types";

const SAFETY_FRAMING =
  "This is a conceptual REI-inspired simulation, not diagnosis, therapy, personality typing, or proof of actual inner structure.";

const FALLBACK_PROFILES: ProfileId[] = [
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
];

const DEFAULT_PROVIDER: ProviderSelection = {
  provider_mode: "ollama",
  racio_model: "granite4.1:30b",
  emocio_model: "granite4.1:30b",
  instinkt_model: "granite4.1:30b",
  synthesis_model: "granite4.1:30b",
  use_llm: true,
  debug_trace: true,
};

const EXAMPLE_OPTIONS = [
  "A quit immediately",
  "B 90-day pilot while employed",
  "C drop the idea",
  "D seek mentor/investor",
];

type Mode = "simple" | "advanced";
type View = "single" | "options" | "trialogue" | "compare" | "history";
type StakeState = {
  financial_risk: number;
  social_exposure: number;
  time_pressure: number;
  relationship_risk: number;
  reversibility: number;
};
type StreamRoleKey = "racio" | "emocio" | "instinkt" | "ego";
type StreamEntry = {
  raw: string;
  status: string;
  model: string;
  label: string;
  doneCount: number;
};

const STREAM_ROLES: Array<{
  key: StreamRoleKey;
  title: string;
  subtitle: string;
}> = [
  {
    key: "racio",
    title: "Racio",
    subtitle: "Words, numbers, sequence",
  },
  {
    key: "emocio",
    title: "Emocio",
    subtitle: "Racio-translated image signal",
  },
  {
    key: "instinkt",
    title: "Instinkt",
    subtitle: "Racio-translated protective signal",
  },
  {
    key: "ego",
    title: "EgoResultant",
    subtitle: "Perceived world and action pressure",
  },
];

export default function App() {
  const [mode, setMode] = useState<Mode>("simple");
  const [profiles, setProfiles] = useState<ProfileId[]>(FALLBACK_PROFILES);
  const [provider, setProvider] = useState<ProviderSelection>(DEFAULT_PROVIDER);
  const [models, setModels] = useState<string[]>(["granite4.1:30b"]);
  const [providerStatus, setProviderStatus] = useState({ ollama: false, lmstudio: false });
  const [runtimeManifest, setRuntimeManifest] = useState<RuntimeManifest | null>(null);

  const [title, setTitle] = useState("quit_job_start_business");
  const [situation, setSituation] = useState(
    "I am considering leaving my job to start a business. The idea feels alive, but the income risk, timing, and social consequences make me hesitate.",
  );
  const [optionsText, setOptionsText] = useState(EXAMPLE_OPTIONS.join("\n"));
  const [profile, setProfile] = useState<ProfileId>("REI");
  const [stakes, setStakes] = useState<StakeState>({
    financial_risk: 0.78,
    social_exposure: 0.56,
    time_pressure: 0.48,
    relationship_risk: 0.52,
    reversibility: 0.44,
  });
  const [compareProfiles, setCompareProfiles] = useState<ProfileId[]>(["R", "E", "I", "REI"]);
  const [userNotes, setUserNotes] = useState("");
  const [useMemory, setUseMemory] = useState(true);
  const [saveObservation, setSaveObservation] = useState(true);

  const [result, setResult] = useState<PlaygroundRunResponse | null>(null);
  const [observations, setObservations] = useState<ObservationSummary[]>([]);
  const [activeView, setActiveView] = useState<View>("single");
  const [instructionRole, setInstructionRole] = useState<StreamRoleKey>("racio");
  const [currentInstructions, setCurrentInstructions] = useState<ProcessorRunInstruction[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [streamEntries, setStreamEntries] = useState<Record<StreamRoleKey, StreamEntry>>(createEmptyStreamState);
  const [statusLines, setStatusLines] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([getRuntimeManifest(), getProfiles(), getProviders(), getObservations()])
      .then(([manifestPayload, profilePayload, providerPayload, observationPayload]) => {
        setRuntimeManifest(manifestPayload);
        setProfiles(profilePayload.profiles.length ? profilePayload.profiles : FALLBACK_PROFILES);
        setModels(
          Array.from(
            new Set(["granite4.1:30b", ...providerPayload.ollama.models, ...providerPayload.lmstudio.models]),
          ),
        );
        setProviderStatus({
          ollama: providerPayload.ollama.available,
          lmstudio: providerPayload.lmstudio.available,
        });
        setObservations(observationPayload.observations);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const options = useMemo(
    () =>
      optionsText
        .split(/\n/)
        .map((item) => item.trim())
        .filter(Boolean),
    [optionsText],
  );

  const selectedOption = result?.option_evaluations.find((item) => item.is_likely_selected);

  async function run() {
    setLoading(true);
    setError(null);
    setResult(null);
    setSelectedHistoryId(null);
    setCurrentInstructions([]);
    setStreamEntries(createEmptyStreamState());
    setStatusLines(["Opening stream"]);
    setActiveView("single");
    try {
      const payload: PlaygroundRequest = {
        provider,
        scenario: {
          title,
          situation,
          decision_options: options,
          stakes,
        },
        profile,
        compare_profiles: mode === "advanced" ? compareProfiles : [],
        user_notes: userNotes,
        acceptance_mode: "unknown",
        use_memory: useMemory,
        save_observation: saveObservation,
      };
      await streamPlayground(payload, handleStreamEvent);
      const observationPayload = await getObservations();
      setObservations(observationPayload.observations);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function openObservation(item: ObservationSummary) {
    setHistoryLoading(true);
    setError(null);
    try {
      const loaded = await getObservation(item.id);
      setResult(loaded);
      setCurrentInstructions(loaded.processor_instructions ?? []);
      setSelectedHistoryId(item.id);
      setStreamEntries(completeStreamEntriesFromResult(createEmptyStreamState(), loaded));
      setStatusLines((previous) => [`Loaded history: ${item.title}`, ...previous].slice(0, 10));
      setActiveView("single");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setHistoryLoading(false);
    }
  }

  function handleStreamEvent(event: StreamEvent) {
    if (event.event === "status") {
      setStatusLines((previous) => [event.data.message, ...previous].slice(0, 10));
      return;
    }
    if (event.event === "processor_instructions") {
      setCurrentInstructions(event.data.instructions);
      setStreamEntries((previous) => hydrateStreamModelsFromInstructions(previous, event.data.instructions));
      return;
    }
    if (event.event === "token") {
      const label = event.data.label ? `[${event.data.label}] ` : "";
      const role = streamRoleFromLabel(event.data.label);
      if (event.data.type === "start") {
        setStatusLines((previous) => [`${label}${event.data.model ?? "model"} started`, ...previous].slice(0, 10));
        setStreamEntries((previous) => {
          const entry = previous[role];
          return {
            ...previous,
            [role]: {
              ...entry,
              raw: entry.raw ? `${entry.raw}\n\n` : entry.raw,
              status: "streaming",
              model: event.data.model ?? entry.model,
              label: event.data.label ?? entry.label,
            },
          };
        });
      }
      if (event.data.content) {
        setStreamEntries((previous) => ({
          ...previous,
          [role]: {
            ...previous[role],
            raw: `${previous[role].raw}${event.data.content}`,
            label: event.data.label ?? previous[role].label,
            model: event.data.model ?? previous[role].model,
            status: "streaming",
          },
        }));
      }
      if (event.data.type === "done") {
        setStatusLines((previous) => [`${label}${event.data.model ?? "model"} done`, ...previous].slice(0, 10));
        setStreamEntries((previous) => ({
          ...previous,
          [role]: {
            ...previous[role],
            status: "complete",
            doneCount: previous[role].doneCount + 1,
            label: event.data.label ?? previous[role].label,
            model: event.data.model ?? previous[role].model,
          },
        }));
      }
      return;
    }
    if (event.event === "compare_result") {
      setStatusLines((previous) => [`Compared ${event.data.profile}`, ...previous].slice(0, 10));
      return;
    }
    if (event.event === "result") {
      setResult(event.data);
      setCurrentInstructions(event.data.processor_instructions ?? []);
      setStreamEntries((previous) => completeStreamEntriesFromResult(previous, event.data));
      setStatusLines((previous) => [
        event.data.observation_path ? "Observation saved" : "Run complete",
        ...previous,
      ].slice(0, 10));
      return;
    }
    if (event.event === "error") {
      setError(event.data.message);
    }
  }

  function updateProvider<K extends keyof ProviderSelection>(key: K, value: ProviderSelection[K]) {
    setProvider((previous) => ({ ...previous, [key]: value }));
  }

  function updateStake<K extends keyof StakeState>(key: K, value: number) {
    setStakes((previous) => ({ ...previous, [key]: value }));
  }

  function toggleCompareProfile(value: ProfileId) {
    setCompareProfiles((previous) =>
      previous.includes(value) ? previous.filter((item) => item !== value) : [...previous, value],
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">REI Playground MVP</p>
          <h1>Observation Framework</h1>
          <RuntimeStackSummary manifest={runtimeManifest} />
        </div>
        <div className="status-strip">
          <StatusPill ok={providerStatus.ollama} label={`Ollama ${providerStatus.ollama ? "available" : "offline"}`} />
          <StatusPill ok={providerStatus.lmstudio} label={`LM Studio ${providerStatus.lmstudio ? "available" : "offline"}`} />
          <span className="status">
            <Server size={16} aria-hidden="true" />
            {API_BASE}
          </span>
        </div>
      </header>

      <SafetyBanner text={SAFETY_FRAMING} />

      <section className="workspace-grid">
        <form className="panel input-panel" onSubmit={(event) => void event.preventDefault()}>
          <div className="panel-header">
            <div>
              <h2>Scenario</h2>
              <span>{mode === "simple" ? "Simple" : "Advanced"}</span>
            </div>
            <SegmentedControl mode={mode} onChange={setMode} />
          </div>

          <label>
            Title
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>

          <label>
            Situation
            <textarea value={situation} onChange={(event) => setSituation(event.target.value)} rows={6} />
          </label>

          <label>
            Decision options
            <textarea value={optionsText} onChange={(event) => setOptionsText(event.target.value)} rows={5} />
          </label>

          <div className="two-col">
            <label>
              Profile
              <select value={profile} onChange={(event) => setProfile(event.target.value as ProfileId)}>
                {profiles.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Provider
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
          </div>

          {mode === "advanced" && (
            <>
              <section className="advanced-band" aria-label="Stakes">
                <div className="section-title">
                  <SlidersHorizontal size={17} aria-hidden="true" />
                  <h3>Stakes</h3>
                </div>
                <div className="stake-grid">
                  <Slider label="Financial risk" value={stakes.financial_risk} onChange={(value) => updateStake("financial_risk", value)} />
                  <Slider label="Social exposure" value={stakes.social_exposure} onChange={(value) => updateStake("social_exposure", value)} />
                  <Slider label="Time pressure" value={stakes.time_pressure} onChange={(value) => updateStake("time_pressure", value)} />
                  <Slider label="Relationship risk" value={stakes.relationship_risk} onChange={(value) => updateStake("relationship_risk", value)} />
                  <Slider label="Reversibility" value={stakes.reversibility} onChange={(value) => updateStake("reversibility", value)} />
                </div>
              </section>

              <section className="advanced-band" aria-label="Models">
                <div className="section-title">
                  <Server size={17} aria-hidden="true" />
                  <h3>Models</h3>
                </div>
                <div className="model-grid">
                  <ModelSelect label="Racio" value={provider.racio_model} models={models} onChange={(value) => updateProvider("racio_model", value)} />
                  <ModelSelect label="Emocio" value={provider.emocio_model} models={models} onChange={(value) => updateProvider("emocio_model", value)} />
                  <ModelSelect label="Instinkt" value={provider.instinkt_model} models={models} onChange={(value) => updateProvider("instinkt_model", value)} />
                  <ModelSelect label="Ego" value={provider.synthesis_model} models={models} onChange={(value) => updateProvider("synthesis_model", value)} />
                </div>
                <div className="toggle-row">
                  <CheckToggle label="LLM" checked={provider.use_llm} onChange={(checked) => updateProvider("use_llm", checked)} />
                  <CheckToggle label="Debug" checked={provider.debug_trace} onChange={(checked) => updateProvider("debug_trace", checked)} />
                  <CheckToggle label="Memory" checked={useMemory} onChange={setUseMemory} />
                  <CheckToggle label="Save" checked={saveObservation} onChange={setSaveObservation} />
                </div>
              </section>

              <section className="advanced-band" aria-label="Profile comparison">
                <div className="section-title">
                  <Users size={17} aria-hidden="true" />
                  <h3>Compare</h3>
                </div>
                <div className="profile-chip-grid">
                  {profiles.map((item) => (
                    <button
                      className={compareProfiles.includes(item) ? "chip active" : "chip"}
                      key={item}
                      type="button"
                      onClick={() => toggleCompareProfile(item)}
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </section>
            </>
          )}

          <label>
            User notes
            <textarea value={userNotes} onChange={(event) => setUserNotes(event.target.value)} rows={3} />
          </label>

          <button className="primary-button" type="button" onClick={run} disabled={loading || !situation.trim()}>
            {loading ? <RefreshCw className="spin" size={18} aria-hidden="true" /> : <Play size={18} aria-hidden="true" />}
            {loading ? "Streaming" : "Run"}
          </button>

          {error && <div className="error-box">{error}</div>}
        </form>

        <aside className="panel stream-panel">
          <div className="panel-header">
            <div>
              <h2>Live Stream</h2>
              <span>{provider.provider_mode}</span>
            </div>
            <ReiRoleIcon role="ego" />
          </div>
          <div className="status-list">
            {statusLines.map((line, index) => (
              <p key={`${line}-${index}`}>{line}</p>
            ))}
          </div>
          <div className="stream-grid" aria-label="Processor token streams">
            {STREAM_ROLES.map((role) => (
              <StreamRoleCard entry={streamEntries[role.key]} key={role.key} role={role.key} />
            ))}
          </div>
          <InstructionInspector
            instructions={result?.processor_instructions ?? currentInstructions}
            role={instructionRole}
            runCaption={result ? `${result.selected_profile} / ${formatDate(result.timestamp)}` : `${provider.provider_mode} current run`}
            onRoleChange={setInstructionRole}
          />
        </aside>
      </section>

      {result && (
        <section className="result-shell">
          <SafetyLine text={result.safety_framing} />
          <nav className="view-tabs" aria-label="Playground views">
            <TabButton active={activeView === "single"} icon={<BrainCircuit size={17} />} label="Single Run" onClick={() => setActiveView("single")} />
            <TabButton active={activeView === "options"} icon={<ListChecks size={17} />} label="Decisions" onClick={() => setActiveView("options")} />
            <TabButton active={activeView === "trialogue"} icon={<MessageSquareText size={17} />} label="Trialogue" onClick={() => setActiveView("trialogue")} />
            <TabButton active={activeView === "compare"} icon={<Users size={17} />} label="Compare" onClick={() => setActiveView("compare")} />
            <TabButton active={activeView === "history"} icon={<History size={17} />} label="History" onClick={() => setActiveView("history")} />
          </nav>

          {activeView === "single" && <SingleRunView result={result} selectedOption={selectedOption?.option ?? ""} />}
          {activeView === "options" && <DecisionView result={result} />}
          {activeView === "trialogue" && <TrialogueView result={result} />}
          {activeView === "compare" && <CompareView result={result} />}
          {activeView === "history" && (
            <ObservationLog
              result={result}
              observations={observations}
              selectedId={selectedHistoryId}
              loading={historyLoading}
              onOpen={openObservation}
            />
          )}
        </section>
      )}
    </main>
  );
}

function SingleRunView({ result, selectedOption }: { result: PlaygroundRunResponse; selectedOption: string }) {
  const cycle = result.processor_outputs;
  return (
    <section className="result-section">
      <div className="summary-grid">
        <SummaryTile label="Profile" value={`${result.selected_profile} -> ${result.canonical_profile}`} />
        <SummaryTile label="Selected option" value={selectedOption || "No option list"} />
        <SummaryTile label="Leader under pressure" value={cycle.ego_resultant.resultant_leader_under_pressure} />
        <SummaryTile label="Smallest next step" value={cycle.ego_resultant.smallest_acceptable_next_step} />
      </div>

      <div className="signals-grid">
        <RacioCard signal={cycle.signals.racio} />
        <EmocioCard signal={cycle.signals.emocio_translated} />
        <InstinktCard signal={cycle.signals.instinkt_translated} />
      </div>

      <div className="analysis-grid">
        <section className="analysis-panel">
          <h3>Acceptance</h3>
          <Field label="Overall" value={cycle.acceptance.overall_level} />
          <Field label="Racio" value={cycle.acceptance.racio_acceptance} />
          <Field label="Emocio" value={cycle.acceptance.emocio_acceptance} />
          <Field label="Instinkt" value={cycle.acceptance.instinkt_acceptance} />
          <Field label="Conflict" value={cycle.acceptance.main_conflict} />
          <Field label="Sabotage point" value={cycle.acceptance.likely_sabotage_point} />
        </section>
        <section className="analysis-panel">
          <h3>EgoResultant</h3>
          <Field label="Perceived world" value={cycle.ego_resultant.perceived_world} />
          <Field label="Action tendency" value={cycle.ego_resultant.action_tendency || cycle.ego_resultant.likely_action_under_pressure} />
          <Field label="Hidden driver" value={cycle.ego_resultant.hidden_driver} />
          <Field label="Hidden cost" value={cycle.ego_resultant.hidden_cost} />
          <Field label="Racio after-story" value={cycle.ego_resultant.racio_justification_afterwards} />
        </section>
      </div>
    </section>
  );
}

function DecisionView({ result }: { result: PlaygroundRunResponse }) {
  if (!result.option_evaluations.length) {
    return <EmptyState text="No decision options were supplied." />;
  }
  return (
    <section className="option-table" aria-label="Decision option evaluation">
      {result.option_evaluations.map((item) => (
        <article className={item.is_likely_selected ? "option-row selected" : "option-row"} key={item.option}>
          <header>
            <strong>{item.option}</strong>
            {item.is_likely_selected && (
              <span>
                <CheckCircle2 size={16} aria-hidden="true" />
                likely selected
              </span>
            )}
          </header>
          <div className="score-row">
            <Score label="Racio" value={item.racio_score} />
            <Score label="Emocio" value={item.emocio_score} />
            <Score label="Instinkt" value={item.instinkt_score} />
          </div>
          <Field label="Racio evaluation" value={item.racio_evaluation} />
          <Field label="Emocio evaluation" value={item.emocio_evaluation} />
          <Field label="Instinkt evaluation" value={item.instinkt_evaluation} />
          <Field label="Ego pressure" value={item.ego_pressure} />
          <Field label="Likely selected option" value={item.likely_selected_option} />
          <Field label="Rejected reason" value={item.rejected_option_reason} />
        </article>
      ))}
    </section>
  );
}

function TrialogueView({ result }: { result: PlaygroundRunResponse }) {
  return (
    <section className="trialogue-view">
      {result.trialogue.rounds.map((round) => (
        <div className="trialogue-round" key={round.round}>
          <h3>
            Round {round.round}: {round.title}
          </h3>
          <div className="trialogue-lines">
            {round.lines.map((line) => (
              <article className={`trialogue-line ${line.processor}`} key={`${round.round}-${line.processor}`}>
                <strong>{line.label}</strong>
                <small>{line.caveat}</small>
                <p>{line.signal}</p>
              </article>
            ))}
          </div>
        </div>
      ))}
      <section className="final-resultant">
        <h3>Final: EgoResultant</h3>
        <Field label="Perceived world" value={result.trialogue.final.perceived_world} />
        <Field label="Action tendency" value={result.trialogue.final.action_tendency} />
      </section>
    </section>
  );
}

function CompareView({ result }: { result: PlaygroundRunResponse }) {
  if (!result.compare_profiles.length) {
    return <EmptyState text="No comparison profiles selected for this run." />;
  }
  return (
    <section className="compare-table" aria-label="Profile comparison">
      <div className="compare-head">
        <span>Profile</span>
        <span>Leader</span>
        <span>Driver</span>
        <span>Pressure</span>
        <span>Selected</span>
        <span>Perceived world</span>
        <span>Hidden driver</span>
        <span>Smallest step</span>
      </div>
      {result.compare_profiles.map((item) => (
        <article className="compare-row" key={item.profile}>
          <strong>{item.profile}</strong>
          <span>{item.profile_leader}</span>
          <span>{item.situational_driver}</span>
          <span>{item.resultant_leader_under_pressure}</span>
          <span>{item.selected_option || "-"}</span>
          <p>{item.perceived_world}</p>
          <p>{item.hidden_driver}</p>
          <p>{item.smallest_next_step}</p>
        </article>
      ))}
    </section>
  );
}

function ObservationLog({
  result,
  observations,
  selectedId,
  loading,
  onOpen,
}: {
  result: PlaygroundRunResponse;
  observations: ObservationSummary[];
  selectedId: string | null;
  loading: boolean;
  onOpen: (item: ObservationSummary) => void;
}) {
  return (
    <section className="log-view">
      <div className="log-current">
        <Save size={19} aria-hidden="true" />
        <div>
          <h3>Observation</h3>
          <p>{result.observation_path ?? "Saving disabled for this run."}</p>
          <small>{result.user_notes || "No user notes."}</small>
        </div>
      </div>
      <div className="observation-list">
        {observations.map((item) => (
          <button
            className={selectedId === item.id ? "observation-item active" : "observation-item"}
            disabled={loading}
            key={item.path}
            type="button"
            onClick={() => onOpen(item)}
          >
            <strong>{item.title}</strong>
            <span>
              {formatDate(item.timestamp)} / {item.selected_profile} / {item.selected_option || "-"}
            </span>
            <small>{item.path}</small>
          </button>
        ))}
      </div>
    </section>
  );
}

function InstructionInspector({
  instructions,
  role,
  runCaption,
  onRoleChange,
}: {
  instructions: ProcessorRunInstruction[];
  role: StreamRoleKey;
  runCaption: string;
  onRoleChange: (role: StreamRoleKey) => void;
}) {
  const instruction = instructionForRole(instructions, role);
  return (
    <section className="instruction-inspector" aria-label="Processor instructions">
      <header>
        <div>
          <h3>Processor Instructions</h3>
          <p>{instructions.length ? runCaption : "No run loaded"}</p>
        </div>
      </header>
      <div className="instruction-role-tabs">
        {STREAM_ROLES.map((item) => (
          <button
            className={role === item.key ? "instruction-role active" : "instruction-role"}
            key={item.key}
            type="button"
            onClick={() => onRoleChange(item.key)}
          >
            <ReiRoleIcon role={item.key} />
            <span>{item.title}</span>
          </button>
        ))}
      </div>
      {instruction ? (
        <div className="instruction-body">
          <Field label="Model" value={instruction.model} />
          <details open>
            <summary>System instruction</summary>
            <pre>{instruction.system_instruction}</pre>
          </details>
          {instruction.user_payload && (
            <details>
              <summary>Run payload</summary>
              <pre>{instruction.user_payload}</pre>
            </details>
          )}
          {Object.keys(instruction.provider_options ?? {}).length > 0 && (
            <details>
              <summary>Provider options</summary>
              <pre>{JSON.stringify(instruction.provider_options, null, 2)}</pre>
            </details>
          )}
        </div>
      ) : (
        <p className="stream-empty">Start a run or load history to inspect processor instructions.</p>
      )}
    </section>
  );
}

function RacioCard({ signal }: { signal: RacioSignal }) {
  return (
    <article className="signal-card racio">
      <SignalHeader title="Racio signal" caveat="Conscious verbal-analytical simulated signal." confidence={signal.confidence} />
      <Field label="Perception" value={signal.perception} />
      <Field label="Preferred action" value={signal.preferred_action} />
      <Field label="Known facts" value={signal.known_facts.join("; ")} />
      <Field label="Unknowns" value={signal.unknowns.join("; ")} />
      <Field label="Utility model" value={signal.utility_model} />
      <Field label="Rationalization risk" value={signal.rationalization_risk} />
    </article>
  );
}

function EmocioCard({ signal }: { signal: EmocioSignal }) {
  return (
    <article className="signal-card emocio">
      <SignalHeader title="Emocio translated signal" caveat="Racio-translated non-verbal image/social/desire signal." confidence={signal.confidence} />
      <Field label="Perception" value={signal.perception} />
      <Field label="Desired image" value={signal.desired_image} />
      <Field label="Social meaning" value={signal.social_meaning} />
      <Field label="Pride / shame" value={signal.pride_or_shame} />
      <Field label="Preferred pressure" value={signal.preferred_action} />
      <Field label="Risk if dominant" value={signal.risk_if_dominant} />
    </article>
  );
}

function InstinktCard({ signal }: { signal: InstinktSignal }) {
  return (
    <article className="signal-card instinkt">
      <SignalHeader title="Instinkt translated signal" caveat="Racio-translated non-verbal protective/body/boundary signal." confidence={signal.confidence} />
      <Field label="Perception" value={signal.perception} />
      <Field label="Threat map" value={signal.threat_map} />
      <Field label="Boundary issue" value={signal.boundary_issue} />
      <Field label="Minimum safety" value={signal.minimum_safety_condition} />
      <Field label="Preferred pressure" value={signal.preferred_action} />
      <Field label="Risk if ignored" value={signal.risk_if_ignored} />
    </article>
  );
}

function SignalHeader({ title, caveat, confidence }: { title: string; caveat: string; confidence: number }) {
  return (
    <header className="signal-header">
      <div>
        <h3>{title}</h3>
        <p>{caveat}</p>
      </div>
      <span>{confidence.toFixed(2)}</span>
    </header>
  );
}

function StreamRoleCard({ role, entry }: { role: StreamRoleKey; entry: StreamEntry }) {
  const roleMeta = STREAM_ROLES.find((item) => item.key === role) ?? STREAM_ROLES[0];
  const fields = parseReadableJsonFields(entry.raw, role);
  const tail = cleanStreamTail(entry.raw);
  return (
    <article className={`stream-role-card ${role}`}>
      <header>
        <ReiRoleIcon role={role} />
        <div>
          <h3>{roleMeta.title}</h3>
          <p>{roleMeta.subtitle}</p>
        </div>
        <span>{entry.status}</span>
      </header>
      {entry.model && <small className="stream-model">{entry.model}</small>}
      <div className="stream-readable">
        {fields.length ? (
          fields.map((field) => (
            <div className="stream-field" key={field.key}>
              <span>{fieldLabel(field.key)}</span>
              <p>{field.value}</p>
            </div>
          ))
        ) : (
          <p className="stream-empty">{tail || "Waiting for this processor."}</p>
        )}
      </div>
    </article>
  );
}

function ReiRoleIcon({ role }: { role: StreamRoleKey }) {
  if (role === "racio") {
    return (
      <svg className="role-icon racio-icon" viewBox="0 0 64 64" aria-hidden="true">
        <circle cx="32" cy="32" r="29" />
        <path d="M20 18h24M20 28h24M20 38h16" />
        <path d="M42 42l7 7M44 34a10 10 0 1 0 0.1 0" />
        <circle cx="23" cy="18" r="2.2" />
        <circle cx="23" cy="28" r="2.2" />
        <circle cx="23" cy="38" r="2.2" />
      </svg>
    );
  }
  if (role === "emocio") {
    return (
      <svg className="role-icon emocio-icon" viewBox="0 0 64 64" aria-hidden="true">
        <circle cx="32" cy="32" r="29" />
        <path d="M32 16c8 5 13 10 13 17 0 8-6 14-13 17-7-3-13-9-13-17 0-7 5-12 13-17Z" />
        <path d="M24 31h16M32 23v24M25 24l14 14M39 24 25 38" />
        <circle cx="32" cy="32" r="5" />
      </svg>
    );
  }
  if (role === "instinkt") {
    return (
      <svg className="role-icon instinkt-icon" viewBox="0 0 64 64" aria-hidden="true">
        <circle cx="32" cy="32" r="29" />
        <path d="M32 14 47 20v12c0 10-6 17-15 20-9-3-15-10-15-20V20l15-6Z" />
        <path d="M24 34a8 8 0 0 1 16 0M22 25c6-5 14-5 20 0" />
        <circle cx="32" cy="35" r="3" />
        <path d="M32 40v6" />
      </svg>
    );
  }
  return (
    <svg className="role-icon ego-icon" viewBox="0 0 64 64" aria-hidden="true">
      <circle cx="32" cy="32" r="29" />
      <circle cx="19" cy="22" r="6" />
      <circle cx="45" cy="22" r="6" />
      <circle cx="32" cy="46" r="6" />
      <path d="M24 24h16M22 28l7 13M42 28l-7 13" />
      <circle cx="32" cy="32" r="8" />
    </svg>
  );
}

function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={ok ? "status ok" : "status warn"}>
      <Server size={16} aria-hidden="true" />
      {label}
    </span>
  );
}

function SafetyBanner({ text }: { text: string }) {
  return (
    <section className="safety-banner">
      <ShieldCheck size={18} aria-hidden="true" />
      <p>{text}</p>
    </section>
  );
}

function SafetyLine({ text }: { text: string }) {
  return (
    <p className="safety-line">
      <ShieldCheck size={15} aria-hidden="true" />
      {text}
    </p>
  );
}

function RuntimeStackSummary({ manifest }: { manifest: RuntimeManifest | null }) {
  if (!manifest) {
    return <p className="stack-line">Runtime stack not loaded</p>;
  }
  const logicId = manifest.active_logic?.id ?? manifest.active.engine.contract_id;
  const motoricsId = manifest.active_motorics?.id ?? manifest.active.engine.id;
  return (
    <div className="version-stack" aria-label="Active runtime stack">
      <span>{manifest.project.active_stack_label}</span>
      <strong>{manifest.project.version}</strong>
      <small>
        logic: {logicId} / motorics: {motoricsId}
      </small>
      <small>
        runtime: {manifest.active.engine.id} -&gt; {manifest.active.playground_api.id} -&gt;{" "}
        {manifest.active.frontend.id}
      </small>
    </div>
  );
}

function SegmentedControl({ mode, onChange }: { mode: Mode; onChange: (mode: Mode) => void }) {
  return (
    <div className="segmented" aria-label="Mode">
      <button className={mode === "simple" ? "active" : ""} type="button" onClick={() => onChange("simple")}>
        Simple
      </button>
      <button className={mode === "advanced" ? "active" : ""} type="button" onClick={() => onChange("advanced")}>
        Advanced
      </button>
    </div>
  );
}

function Slider({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
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

function CheckToggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="check-toggle">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function TabButton({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button className={active ? "tab active" : "tab"} type="button" onClick={onClick}>
      {icon}
      {label}
    </button>
  );
}

function SummaryTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="summary-tile">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string | number | null }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="field">
      <span>{label}</span>
      <p>{value}</p>
    </div>
  );
}

function Score({ label, value }: { label: string; value: number }) {
  return (
    <div className="score">
      <span>{label}</span>
      <strong>{value.toFixed(2)}</strong>
      <i style={{ width: `${Math.round(value * 100)}%` }} />
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="empty-state">{text}</p>;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function createEmptyStreamState(): Record<StreamRoleKey, StreamEntry> {
  return {
    racio: { raw: "", status: "idle", model: "", label: "", doneCount: 0 },
    emocio: { raw: "", status: "idle", model: "", label: "", doneCount: 0 },
    instinkt: { raw: "", status: "idle", model: "", label: "", doneCount: 0 },
    ego: { raw: "", status: "idle", model: "", label: "", doneCount: 0 },
  };
}

function completeStreamEntriesFromResult(
  previous: Record<StreamRoleKey, StreamEntry>,
  result: PlaygroundRunResponse,
): Record<StreamRoleKey, StreamEntry> {
  const cycle = result.processor_outputs;
  const instructionMap = new Map(
    (result.processor_instructions ?? []).map((item) => [instructionRoleFromProcessor(item.processor), item]),
  );
  const payloads: Record<StreamRoleKey, unknown> = {
    racio: cycle.signals.racio,
    emocio: cycle.signals.emocio_translated,
    instinkt: cycle.signals.instinkt_translated,
    ego: cycle.ego_resultant,
  };
  return STREAM_ROLES.reduce(
    (next, role) => {
      const current = previous[role.key];
      next[role.key] = {
        ...current,
        raw: current.raw || JSON.stringify(payloads[role.key], null, 2),
        label: current.label || instructionMap.get(role.key)?.label || role.title,
        model: current.model || instructionMap.get(role.key)?.model || "",
        status: "complete",
      };
      return next;
    },
    { ...previous },
  );
}

function hydrateStreamModelsFromInstructions(
  previous: Record<StreamRoleKey, StreamEntry>,
  instructions: ProcessorRunInstruction[],
): Record<StreamRoleKey, StreamEntry> {
  const next = { ...previous };
  for (const instruction of instructions) {
    const role = instructionRoleFromProcessor(instruction.processor);
    next[role] = {
      ...next[role],
      label: next[role].label || instruction.label,
      model: next[role].model || instruction.model,
    };
  }
  return next;
}

function instructionForRole(
  instructions: ProcessorRunInstruction[],
  role: StreamRoleKey,
): ProcessorRunInstruction | null {
  return instructions.find((item) => instructionRoleFromProcessor(item.processor) === role) ?? null;
}

function instructionRoleFromProcessor(processor: string): StreamRoleKey {
  const normalized = processor.toLowerCase();
  if (normalized.includes("emocio")) return "emocio";
  if (normalized.includes("instinkt")) return "instinkt";
  if (normalized.includes("ego") || normalized.includes("synthesis")) return "ego";
  return "racio";
}

function streamRoleFromLabel(label?: string): StreamRoleKey {
  const normalized = (label ?? "").toLowerCase();
  if (normalized.includes("emocio")) return "emocio";
  if (normalized.includes("instinkt")) return "instinkt";
  if (normalized.includes("ego") || normalized === "s") return "ego";
  return "racio";
}

function parseReadableJsonFields(raw: string, role: StreamRoleKey): Array<{ key: string; value: string }> {
  const trimmed = raw.trim();
  if (!trimmed) return [];
  const parsed = tryParseJsonObject(trimmed);
  const values = parsed ? objectFields(parsed) : regexFields(trimmed);
  const priority = fieldPriority(role);
  const ordered = [
    ...priority.filter((key) => values.has(key)),
    ...Array.from(values.keys()).filter((key) => !priority.includes(key)),
  ];
  return ordered
    .map((key) => ({ key, value: values.get(key) ?? "" }))
    .filter((field) => field.value)
    .slice(0, 6);
}

function tryParseJsonObject(raw: string): Record<string, unknown> | null {
  const start = raw.indexOf("{");
  const end = raw.lastIndexOf("}");
  if (start < 0 || end <= start) return null;
  try {
    const parsed = JSON.parse(raw.slice(start, end + 1));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function objectFields(parsed: Record<string, unknown>): Map<string, string> {
  const fields = new Map<string, string>();
  for (const [key, value] of Object.entries(parsed)) {
    const rendered = renderStreamValue(value);
    if (rendered) fields.set(key, rendered);
  }
  return fields;
}

function regexFields(raw: string): Map<string, string> {
  const fields = new Map<string, string>();
  const pattern = /"([A-Za-z0-9_]+)"\s*:\s*"((?:\\.|[^"\\])*)"/g;
  let match = pattern.exec(raw);
  while (match) {
    const value = safeJsonString(match[2]);
    if (value) fields.set(match[1], value);
    match = pattern.exec(raw);
  }
  return fields;
}

function safeJsonString(value: string): string {
  try {
    return JSON.parse(`"${value}"`);
  } catch {
    return value.replace(/\\"/g, '"').replace(/\\n/g, " ");
  }
}

function renderStreamValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    return value
      .map((item) => renderStreamValue(item))
      .filter(Boolean)
      .join("; ");
  }
  return "";
}

function fieldPriority(role: StreamRoleKey): string[] {
  if (role === "racio") {
    return [
      "perception",
      "preferred_action",
      "known_facts",
      "unknowns",
      "utility_model",
      "rationalization_risk",
    ];
  }
  if (role === "emocio") {
    return ["perception", "desired_image", "social_meaning", "pride_or_shame", "preferred_action"];
  }
  if (role === "instinkt") {
    return ["perception", "threat_map", "boundary_issue", "minimum_safety_condition", "preferred_action"];
  }
  return [
    "perceived_world",
    "action_tendency",
    "likely_action_under_pressure",
    "hidden_driver",
    "smallest_acceptable_next_step",
  ];
}

function fieldLabel(key: string): string {
  return key.replace(/_/g, " ");
}

function cleanStreamTail(raw: string): string {
  if (!raw.trim()) return "";
  return raw
    .slice(-520)
    .replace(/[{}[\]",]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
