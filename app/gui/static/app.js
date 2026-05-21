const targets = ["racio", "emocio", "instinkt", "ego_resultant"];
const processorTargets = ["racio", "emocio", "instinkt"];
const labels = {
  racio: "Racio",
  emocio: "Emocio",
  instinkt: "Instinkt",
  ego_resultant: "EgoResultant",
};

const state = {
  prompts: {},
  models: [],
  running: [],
  defaults: {},
  activePrompt: "racio",
  activeRunId: null,
  activeReader: null,
  outputs: {},
  parsed: {},
  settings: {},
  history: [],
};

const els = {
  ollamaStatus: document.querySelector("#ollamaStatus"),
  refreshModelsBtn: document.querySelector("#refreshModelsBtn"),
  clearHistoryBtn: document.querySelector("#clearHistoryBtn"),
  promptTabs: document.querySelector("#promptTabs"),
  promptMeta: document.querySelector("#promptMeta"),
  promptEditor: document.querySelector("#promptEditor"),
  savePromptBtn: document.querySelector("#savePromptBtn"),
  resetPromptBtn: document.querySelector("#resetPromptBtn"),
  requiredKeys: document.querySelector("#requiredKeys"),
  testInput: document.querySelector("#testInput"),
  profileSelect: document.querySelector("#profileSelect"),
  referenceToggle: document.querySelector("#referenceToggle"),
  settingsGrid: document.querySelector("#settingsGrid"),
  runFullBtn: document.querySelector("#runFullBtn"),
  stopBtn: document.querySelector("#stopBtn"),
  activeRun: document.querySelector("#activeRun"),
  outputGrid: document.querySelector("#outputGrid"),
  historyList: document.querySelector("#historyList"),
  historyCount: document.querySelector("#historyCount"),
};

function loadLocalSettings() {
  try {
    return JSON.parse(localStorage.getItem("reiWorkbenchSettings") || "{}");
  } catch {
    return {};
  }
}

function saveLocalSettings() {
  localStorage.setItem("reiWorkbenchSettings", JSON.stringify(state.settings));
}

function targetDefaults(target) {
  return {
    model: state.defaults.model || state.models[0] || "",
    num_ctx: state.defaults.num_ctx || 65536,
    num_gpu: state.defaults.num_gpu ?? 999,
    temperature: state.defaults.temperature?.[target] ?? null,
    top_p: state.defaults.top_p?.[target] ?? null,
    num_predict: state.defaults.num_predict?.[target] ?? null,
  };
}

function mergedSettings(target) {
  return { ...targetDefaults(target), ...(state.settings[target] || {}) };
}

async function apiJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}

async function loadState() {
  const data = await apiJson("/api/state");
  state.prompts = data.prompts;
  state.models = data.ollama.models || [];
  state.running = data.ollama.running || [];
  state.defaults = data.defaults || {};
  state.history = data.history || [];
  state.settings = { ...Object.fromEntries(targets.map((target) => [target, targetDefaults(target)])), ...loadLocalSettings() };
  renderOllama(data.ollama);
  renderProfiles();
  renderPromptTabs();
  renderPromptEditor();
  renderSettings();
  renderOutputs();
  renderHistory();
}

function renderOllama(ollama) {
  const reachable = ollama.reachable ? "reachable" : "offline";
  const running = (ollama.running || []).length ? `active: ${(ollama.running || []).join(", ")}` : "no active model";
  els.ollamaStatus.textContent = `Ollama ${reachable} · ${ollama.models.length} models · ${running}`;
  els.ollamaStatus.dataset.state = ollama.reachable ? "ok" : "bad";
}

function renderProfiles() {
  els.profileSelect.innerHTML = "";
  for (const profile of state.defaults.profiles || ["REI"]) {
    const option = document.createElement("option");
    option.value = profile;
    option.textContent = profile;
    if (profile === (state.defaults.profile || "REI")) option.selected = true;
    els.profileSelect.append(option);
  }
}

function renderPromptTabs() {
  els.promptTabs.innerHTML = "";
  for (const target of targets) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = labels[target];
    button.className = target === state.activePrompt ? "active" : "";
    button.addEventListener("click", () => {
      state.activePrompt = target;
      renderPromptTabs();
      renderPromptEditor();
    });
    els.promptTabs.append(button);
  }
}

function renderPromptEditor() {
  const entry = state.prompts[state.activePrompt];
  if (!entry) return;
  els.promptEditor.value = entry.prompt || "";
  els.promptMeta.textContent = `${entry.has_override ? "override" : "baseline"} · ${entry.prompt_hash}`;
  els.promptMeta.dataset.state = entry.has_override ? "warn" : "ok";
  const keys = entry.required_keys || [];
  els.requiredKeys.textContent = `${keys.length} required keys: ${keys.join(", ")}`;
}

function renderSettings() {
  els.settingsGrid.innerHTML = "";
  for (const target of targets) {
    const settings = mergedSettings(target);
    const panel = document.createElement("section");
    panel.className = `settings-panel ${target}`;
    panel.innerHTML = `
      <div class="settings-title">${labels[target]}</div>
      <label class="field">
        <span>Model</span>
        <select data-setting="${target}" data-key="model"></select>
      </label>
      <div class="mini-grid">
        <label class="field">
          <span>num_ctx</span>
          <input data-setting="${target}" data-key="num_ctx" type="number" min="512" max="262144" step="512" value="${settings.num_ctx}" />
        </label>
        <label class="field">
          <span>num_gpu</span>
          <input data-setting="${target}" data-key="num_gpu" type="number" min="0" max="999" step="1" value="${settings.num_gpu}" />
        </label>
      </div>
    `;
    const select = panel.querySelector("select");
    if (!state.models.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No models";
      select.append(option);
    } else {
      for (const model of state.models) {
        const option = document.createElement("option");
        option.value = model;
        option.textContent = model;
        if (model === settings.model) option.selected = true;
        select.append(option);
      }
    }
    panel.querySelectorAll("[data-setting]").forEach((input) => {
      input.addEventListener("change", () => {
        const targetName = input.dataset.setting;
        const key = input.dataset.key;
        const next = { ...mergedSettings(targetName) };
        next[key] = input.type === "number" ? Number(input.value) : input.value;
        state.settings[targetName] = next;
        saveLocalSettings();
      });
    });
    els.settingsGrid.append(panel);
  }
}

function renderOutputs() {
  els.outputGrid.innerHTML = "";
  for (const target of targets) {
    const output = state.outputs[target] || { text: "", status: "idle", meta: "" };
    const panel = document.createElement("section");
    panel.className = `output-panel ${target}`;
    panel.innerHTML = `
      <div class="output-head">
        <h3>${labels[target]}</h3>
        <span class="status">${output.status || "idle"}</span>
      </div>
      <div class="output-meta">${output.meta || ""}</div>
      <pre>${escapeHtml(output.text || "")}</pre>
    `;
    els.outputGrid.append(panel);
  }
}

function renderHistory() {
  els.historyList.innerHTML = "";
  els.historyCount.textContent = String(state.history.length);
  if (!state.history.length) {
    const empty = document.createElement("div");
    empty.className = "history-empty";
    empty.textContent = "No history";
    els.historyList.append(empty);
    return;
  }
  for (const item of state.history) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "history-item";
    button.innerHTML = `
      <span>${formatTime(item.created_at)} · ${escapeHtml(item.mode || "")} · ${escapeHtml(item.status || "")}</span>
      <strong>${escapeHtml((item.input || "").slice(0, 90))}</strong>
    `;
    button.addEventListener("click", () => loadHistoryItem(item));
    els.historyList.append(button);
  }
}

function loadHistoryItem(item) {
  for (const target of targets) {
    const output = item.outputs?.[target];
    if (!output) continue;
    state.outputs[target] = {
      text: output.content || JSON.stringify(output.parsed || {}, null, 2),
      status: output.status || "done",
      meta: output.error || metaFromOutput(output),
    };
    if (output.parsed) state.parsed[target] = output.parsed;
  }
  renderOutputs();
}

function metaFromOutput(output) {
  const missing = output.missing_required_keys || [];
  const speed = output.stats?.eval_tokens_per_second;
  const timing = output.elapsed_ms ? `${output.elapsed_ms} ms` : "";
  const miss = missing.length ? `missing: ${missing.join(", ")}` : "keys ok";
  return [miss, speed ? `${speed} tok/s` : "", timing].filter(Boolean).join(" · ");
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function savePrompt() {
  const target = state.activePrompt;
  const payload = await apiJson(`/api/prompts/${target}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: els.promptEditor.value }),
  });
  state.prompts[target] = { ...state.prompts[target], ...payload };
  renderPromptEditor();
}

async function resetPrompt() {
  const target = state.activePrompt;
  const payload = await apiJson(`/api/prompts/${target}/reset`, { method: "POST" });
  state.prompts[target] = { ...state.prompts[target], ...payload };
  renderPromptEditor();
}

function runPayload(runId) {
  return {
    run_id: runId,
    input: els.testInput.value,
    profile: els.profileSelect.value,
    use_reference_context: els.referenceToggle.checked,
    settings: Object.fromEntries(targets.map((target) => [target, mergedSettings(target)])),
    signals: {
      racio: state.parsed.racio || {},
      emocio: state.parsed.emocio || {},
      instinkt: state.parsed.instinkt || {},
    },
  };
}

async function runEndpoint(endpoint, clearTargets) {
  if (state.activeRunId) return;
  const runId = crypto.randomUUID();
  state.activeRunId = runId;
  els.activeRun.textContent = runId.slice(0, 8);
  els.stopBtn.disabled = false;
  for (const target of clearTargets) {
    state.outputs[target] = { text: "", status: "queued", meta: "" };
    if (target !== "ego_resultant") delete state.parsed[target];
  }
  if (clearTargets.includes("ego_resultant")) delete state.parsed.ego_resultant;
  renderOutputs();

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(runPayload(runId)),
    });
    if (!response.ok || !response.body) {
      throw new Error(await response.text());
    }
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    state.activeReader = reader;
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        handleEvent(JSON.parse(line));
      }
    }
  } catch (error) {
    els.activeRun.textContent = `error`;
    console.error(error);
  } finally {
    state.activeRunId = null;
    state.activeReader = null;
    els.stopBtn.disabled = true;
    if (els.activeRun.textContent !== "error") els.activeRun.textContent = "idle";
  }
}

function handleEvent(event) {
  const target = event.target;
  if (event.type === "start") {
    state.outputs[target] = {
      text: "",
      status: "streaming",
      meta: `${event.model} · ${event.options?.num_ctx || ""} ctx · gpu ${event.options?.num_gpu ?? ""}`,
    };
  } else if (event.type === "delta") {
    const output = state.outputs[target] || { text: "", status: "streaming", meta: "" };
    output.text += event.content || "";
    output.status = "streaming";
    state.outputs[target] = output;
  } else if (event.type === "done") {
    state.outputs[target] = {
      text: event.content || "",
      status: event.status || "done",
      meta: event.error || metaFromOutput(event),
    };
    if (event.parsed) state.parsed[target] = event.parsed;
  } else if (event.type === "stopped") {
    const output = state.outputs[target] || { text: "", status: "stopped", meta: "" };
    output.status = "stopped";
    state.outputs[target] = output;
  } else if (event.type === "error") {
    state.outputs[target] = {
      text: state.outputs[target]?.text || "",
      status: "error",
      meta: event.error || "error",
    };
  } else if (event.type === "run_done") {
    state.history = [event.record, ...state.history.filter((item) => item.id !== event.record.id)];
    renderHistory();
  }
  renderOutputs();
}

async function stopRun() {
  if (!state.activeRunId) return;
  els.stopBtn.disabled = true;
  els.activeRun.textContent = "stopping";
  await fetch(`/api/runs/${state.activeRunId}/stop`, { method: "POST" });
}

async function refreshModels() {
  const data = await apiJson("/api/models");
  state.models = data.models || [];
  state.running = data.running || [];
  renderOllama(data);
  renderSettings();
}

async function clearHistory() {
  const data = await apiJson("/api/history/clear", { method: "POST" });
  state.history = data.history || [];
  renderHistory();
}

els.savePromptBtn.addEventListener("click", savePrompt);
els.resetPromptBtn.addEventListener("click", resetPrompt);
els.refreshModelsBtn.addEventListener("click", refreshModels);
els.clearHistoryBtn.addEventListener("click", clearHistory);
els.stopBtn.addEventListener("click", stopRun);
els.runFullBtn.addEventListener("click", () => runEndpoint("/api/run/full", targets));
document.querySelectorAll("[data-run='mind']").forEach((button) => {
  button.addEventListener("click", () => {
    const target = button.dataset.target;
    runEndpoint(`/api/run/mind/${target}`, [target]);
  });
});
document.querySelector("[data-run='ego']").addEventListener("click", () => runEndpoint("/api/run/ego", ["ego_resultant"]));

loadState().catch((error) => {
  els.ollamaStatus.textContent = `Workbench failed: ${error.message}`;
  els.ollamaStatus.dataset.state = "bad";
});
