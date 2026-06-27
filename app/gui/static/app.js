const targets = ["racio", "emocio", "instinkt", "ego_resultant"];
const processorTargets = ["racio", "emocio", "instinkt"];
const labels = {
  racio: "Racio",
  emocio: "Emocio",
  instinkt: "Instinkt",
  ego_resultant: "EgoResultant",
};
const rawJsonView = "__raw_json__";

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
  outputViews: {},
  history: [],
  datasets: [],
  activeDatasetId: "",
  datasetExamples: [],
  activeDatasetExample: null,
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
  datasetSummary: document.querySelector("#datasetSummary"),
  datasetSelect: document.querySelector("#datasetSelect"),
  datasetTargetFilter: document.querySelector("#datasetTargetFilter"),
  datasetStatusFilter: document.querySelector("#datasetStatusFilter"),
  datasetProfileFilter: document.querySelector("#datasetProfileFilter"),
  refreshDatasetsBtn: document.querySelector("#refreshDatasetsBtn"),
  validateDatasetBtn: document.querySelector("#validateDatasetBtn"),
  exportDatasetBtn: document.querySelector("#exportDatasetBtn"),
  datasetList: document.querySelector("#datasetList"),
  datasetScenario: document.querySelector("#datasetScenario"),
  datasetValidation: document.querySelector("#datasetValidation"),
  datasetStatusSelect: document.querySelector("#datasetStatusSelect"),
  datasetSplitSelect: document.querySelector("#datasetSplitSelect"),
  datasetReviewer: document.querySelector("#datasetReviewer"),
  datasetNotes: document.querySelector("#datasetNotes"),
  datasetJsonEditor: document.querySelector("#datasetJsonEditor"),
  saveDatasetExampleBtn: document.querySelector("#saveDatasetExampleBtn"),
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

function loadLocalOutputViews() {
  try {
    return JSON.parse(localStorage.getItem("reiWorkbenchOutputViews") || "{}");
  } catch {
    return {};
  }
}

function saveLocalOutputViews() {
  localStorage.setItem("reiWorkbenchOutputViews", JSON.stringify(state.outputViews));
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
  state.outputViews = { ...Object.fromEntries(targets.map((target) => [target, rawJsonView])), ...loadLocalOutputViews() };
  renderOllama(data.ollama);
  renderProfiles();
  renderPromptTabs();
  renderPromptEditor();
  renderSettings();
  renderOutputs();
  renderHistory();
  await loadDatasets();
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
    const tags = outputTags(target);
    const selectedView = selectedOutputView(target, tags, output);
    const outputText = outputTextForView(target, selectedView);
    const panel = document.createElement("section");
    panel.className = `output-panel ${target}`;
    panel.innerHTML = `
      <div class="output-head">
        <h3>${labels[target]}</h3>
        <span class="status">${output.status || "idle"}</span>
      </div>
      <div class="output-meta">${output.meta || ""}</div>
      <div class="output-view">
        <label>
          <span>View</span>
          <select data-output-view="${target}">
            ${outputViewOptions(target, tags, selectedView)}
          </select>
        </label>
      </div>
      <pre>${escapeHtml(outputText)}</pre>
    `;
    panel.querySelector("[data-output-view]").addEventListener("change", (event) => {
      state.outputViews[target] = event.target.value;
      saveLocalOutputViews();
      renderOutputs();
    });
    els.outputGrid.append(panel);
  }
}

function outputViewOptions(target, tags, selectedView) {
  const available = new Set(tags);
  const options = tags.map((tag) => {
    const label = tag === rawJsonView ? "RAW JSON" : tag;
    return `<option value="${escapeHtml(tag)}" ${tag === selectedView ? "selected" : ""}>${escapeHtml(label)}</option>`;
  });
  if (selectedView !== rawJsonView && !available.has(selectedView)) {
    options.push(
      `<option value="${escapeHtml(selectedView)}" selected>${escapeHtml(`${selectedView} (not in output yet)`)}</option>`
    );
  }
  return options.join("");
}

function outputTags(target) {
  const output = state.outputs[target] || {};
  const parsed = output.parsed || state.parsed[target];
  const keys =
    parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? Object.keys(parsed)
      : topLevelKeysFromJsonText(output.text || "");
  return [rawJsonView, ...keys.filter((key, index, list) => key && list.indexOf(key) === index)];
}

function selectedOutputView(target, tags, output) {
  const current = state.outputViews[target] || rawJsonView;
  if (current === rawJsonView || tags.includes(current)) {
    return current;
  }
  const finalStatus = ["done", "error", "stopped"].includes(output.status);
  if (finalStatus && (output.text || output.parsed)) {
    state.outputViews[target] = rawJsonView;
    saveLocalOutputViews();
    return rawJsonView;
  }
  return current;
}

function outputTextForView(target, selectedView) {
  const output = state.outputs[target] || {};
  const parsed = output.parsed || state.parsed[target];
  if (selectedView === rawJsonView) {
    if (output.text) return output.text;
    return parsed ? JSON.stringify(parsed, null, 2) : "";
  }
  if (parsed && typeof parsed === "object" && !Array.isArray(parsed) && Object.hasOwn(parsed, selectedView)) {
    return formatJsonValue(parsed[selectedView]);
  }
  const partial = topLevelValueFromJsonText(output.text || "", selectedView);
  if (partial) {
    const prefix = partial.complete ? "" : `Incomplete field "${selectedView}"\n\n`;
    return `${prefix}${partial.value}`;
  }
  return output.text ? `Field "${selectedView}" is not available in this output.` : "";
}

function formatJsonValue(value) {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function decodeJsonString(raw) {
  try {
    return JSON.parse(`"${raw}"`);
  } catch {
    return raw.replace(/\\"/g, '"').replace(/\\\\/g, "\\");
  }
}

function topLevelKeysFromJsonText(text) {
  const keys = [];
  let depth = 0;
  let inString = false;
  let escaped = false;
  let stringStart = -1;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === '"') {
        const raw = text.slice(stringStart + 1, index);
        inString = false;
        if (depth === 1 && nextNonWhitespace(text, index + 1) === ":") {
          keys.push(decodeJsonString(raw));
        }
      }
      continue;
    }
    if (char === '"') {
      inString = true;
      stringStart = index;
    } else if (char === "{" || char === "[") {
      depth += 1;
    } else if (char === "}" || char === "]") {
      depth = Math.max(0, depth - 1);
    }
  }
  return keys;
}

function nextNonWhitespace(text, start) {
  for (let index = start; index < text.length; index += 1) {
    const char = text[index];
    if (!/\s/.test(char)) return char;
  }
  return "";
}

function topLevelValueFromJsonText(text, key) {
  const keyEnd = topLevelKeyEndIndex(text, key);
  if (keyEnd < 0) return null;
  let colon = keyEnd + 1;
  while (colon < text.length && /\s/.test(text[colon])) colon += 1;
  if (text[colon] !== ":") return null;
  let start = colon + 1;
  while (start < text.length && /\s/.test(text[start])) start += 1;
  if (start >= text.length) return { value: "", complete: false };
  const extracted = extractJsonValueText(text, start);
  if (!extracted) return null;
  const rawValue = extracted.value.trim();
  if (extracted.complete) {
    try {
      return { value: formatJsonValue(JSON.parse(rawValue)), complete: true };
    } catch {
      return { value: rawValue, complete: true };
    }
  }
  return { value: rawValue, complete: false };
}

function topLevelKeyEndIndex(text, wantedKey) {
  let depth = 0;
  let inString = false;
  let escaped = false;
  let stringStart = -1;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === '"') {
        const raw = text.slice(stringStart + 1, index);
        inString = false;
        if (depth === 1 && nextNonWhitespace(text, index + 1) === ":" && decodeJsonString(raw) === wantedKey) {
          return index;
        }
      }
      continue;
    }
    if (char === '"') {
      inString = true;
      stringStart = index;
    } else if (char === "{" || char === "[") {
      depth += 1;
    } else if (char === "}" || char === "]") {
      depth = Math.max(0, depth - 1);
    }
  }
  return -1;
}

function extractJsonValueText(text, start) {
  const first = text[start];
  if (first === '"') return extractStringValue(text, start);
  if (first === "{" || first === "[") return extractContainerValue(text, start);
  return extractPrimitiveValue(text, start);
}

function extractStringValue(text, start) {
  let escaped = false;
  for (let index = start + 1; index < text.length; index += 1) {
    const char = text[index];
    if (escaped) {
      escaped = false;
    } else if (char === "\\") {
      escaped = true;
    } else if (char === '"') {
      return { value: text.slice(start, index + 1), complete: true };
    }
  }
  return { value: text.slice(start), complete: false };
}

function extractContainerValue(text, start) {
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = start; index < text.length; index += 1) {
    const char = text[index];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === '"') {
        inString = false;
      }
      continue;
    }
    if (char === '"') {
      inString = true;
    } else if (char === "{" || char === "[") {
      depth += 1;
    } else if (char === "}" || char === "]") {
      depth -= 1;
      if (depth === 0) {
        return { value: text.slice(start, index + 1), complete: true };
      }
    }
  }
  return { value: text.slice(start), complete: false };
}

function extractPrimitiveValue(text, start) {
  for (let index = start; index < text.length; index += 1) {
    const char = text[index];
    if (char === "," || char === "}") {
      return { value: text.slice(start, index), complete: true };
    }
  }
  return { value: text.slice(start), complete: false };
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
      parsed: output.parsed || null,
      status: output.status || "done",
      meta: output.error || metaFromOutput(output),
    };
    if (output.parsed) state.parsed[target] = output.parsed;
  }
  renderOutputs();
}

async function loadDatasets() {
  try {
    const data = await apiJson("/api/datasets");
    state.datasets = data.datasets || [];
    if (!state.activeDatasetId && state.datasets.length) {
      state.activeDatasetId = state.datasets[0].dataset_id;
    }
    renderDatasetSelect();
    if (state.activeDatasetId) {
      await loadDatasetDetail(state.activeDatasetId);
    } else {
      state.datasetExamples = [];
      state.activeDatasetExample = null;
      renderDatasetPanel();
    }
  } catch (error) {
    state.datasets = [];
    state.datasetExamples = [];
    state.activeDatasetExample = null;
    if (els.datasetSummary) {
      els.datasetSummary.textContent = `dataset error`;
      els.datasetSummary.dataset.state = "bad";
    }
    console.error(error);
  }
}

function renderDatasetSelect() {
  if (!els.datasetSelect) return;
  els.datasetSelect.innerHTML = "";
  if (!state.datasets.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No datasets";
    els.datasetSelect.append(option);
    return;
  }
  for (const dataset of state.datasets) {
    const option = document.createElement("option");
    option.value = dataset.dataset_id;
    option.textContent = dataset.dataset_id;
    if (dataset.dataset_id === state.activeDatasetId) option.selected = true;
    els.datasetSelect.append(option);
  }
}

async function loadDatasetDetail(datasetId) {
  const data = await apiJson(`/api/datasets/${encodeURIComponent(datasetId)}`);
  const existingId = state.activeDatasetExample?.example_id || "";
  state.activeDatasetId = datasetId;
  state.datasetExamples = data.examples || [];
  state.activeDatasetExample =
    state.datasetExamples.find((item) => item.example_id === existingId) || state.datasetExamples[0] || null;
  renderDatasetSummary(data);
  renderDatasetPanel();
  if (state.activeDatasetExample) {
    await loadDatasetExample(state.activeDatasetExample.example_id);
  }
}

function renderDatasetSummary(datasetDetail) {
  const validation = datasetDetail?.validation || datasetDetail?.manifest || {};
  const examples = validation.example_count ?? datasetDetail?.manifest?.example_count ?? 0;
  const scenarios = validation.scenario_count ?? datasetDetail?.manifest?.scenario_count ?? 0;
  const invalid = validation.invalid_example_count ?? 0;
  els.datasetSummary.textContent = `${scenarios} scenarios · ${examples} examples · ${invalid} invalid`;
  els.datasetSummary.dataset.state = invalid ? "warn" : "ok";
}

function filteredDatasetExamples() {
  const target = els.datasetTargetFilter?.value || "";
  const status = els.datasetStatusFilter?.value || "";
  const profile = els.datasetProfileFilter?.value || "";
  return state.datasetExamples.filter((item) => {
    if (target && item.target !== target) return false;
    if (status && item.status !== status) return false;
    if (profile && item.character_profile !== profile) return false;
    return true;
  });
}

function renderDatasetPanel() {
  renderDatasetSelect();
  renderDatasetProfileFilter();
  renderDatasetList();
  renderDatasetEditor();
}

function renderDatasetProfileFilter() {
  if (!els.datasetProfileFilter) return;
  const current = els.datasetProfileFilter.value || "";
  const profiles = [...new Set(state.datasetExamples.map((item) => item.character_profile).filter(Boolean))].sort();
  els.datasetProfileFilter.innerHTML = '<option value="">All</option>';
  for (const profile of profiles) {
    const option = document.createElement("option");
    option.value = profile;
    option.textContent = profile;
    els.datasetProfileFilter.append(option);
  }
  els.datasetProfileFilter.value = profiles.includes(current) ? current : "";
}

function renderDatasetList() {
  if (!els.datasetList) return;
  els.datasetList.innerHTML = "";
  const examples = filteredDatasetExamples();
  if (!examples.length) {
    const empty = document.createElement("div");
    empty.className = "history-empty";
    empty.textContent = state.activeDatasetId ? "No matching examples" : "No dataset";
    els.datasetList.append(empty);
    return;
  }
  for (const item of examples) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `dataset-item ${state.activeDatasetExample?.example_id === item.example_id ? "active" : ""}`;
    const valid = item.valid ? "valid" : "invalid";
    const profile = item.character_profile ? item.character_profile : "";
    const review = item.review_only ? "review" : "";
    const meta = [item.target, profile, item.status, valid, review].filter(Boolean).join(" · ");
    button.innerHTML = `
      <span>${escapeHtml(meta)}</span>
      <strong>${escapeHtml(item.scenario_title || item.scenario_id)}</strong>
      <span>${escapeHtml((item.scenario_prompt || "").slice(0, 120))}</span>
    `;
    button.addEventListener("click", () => loadDatasetExample(item.example_id));
    els.datasetList.append(button);
  }
}

async function loadDatasetExample(exampleId) {
  if (!state.activeDatasetId) return;
  const data = await apiJson(
    `/api/datasets/${encodeURIComponent(state.activeDatasetId)}/examples/${encodeURIComponent(exampleId)}`
  );
  state.activeDatasetExample = data.example;
  renderDatasetPanel();
}

function renderDatasetEditor() {
  const example = state.activeDatasetExample;
  if (!els.datasetJsonEditor) return;
  if (!example) {
    els.datasetScenario.textContent = state.activeDatasetId ? "Select a dataset example." : "No dataset available.";
    els.datasetValidation.textContent = "";
    els.datasetValidation.dataset.state = "";
    els.datasetStatusSelect.value = "draft";
    els.datasetSplitSelect.value = "";
    els.datasetReviewer.value = "";
    els.datasetNotes.value = "";
    els.datasetJsonEditor.value = "";
    return;
  }
  const scenario = example.scenario || {};
  const profile = example.character_profile ? ` · ${example.character_profile}` : "";
  els.datasetScenario.innerHTML = `
    <strong>${escapeHtml(`${example.target}${profile} · ${scenario.title || example.scenario_id}`)}</strong>
    ${escapeHtml(scenario.prompt || "")}
  `;
  els.datasetStatusSelect.value = example.status || "draft";
  els.datasetSplitSelect.value = example.split || "";
  els.datasetReviewer.value = example.reviewer || "";
  els.datasetNotes.value = example.review_notes || "";
  els.datasetJsonEditor.value = JSON.stringify(example.assistant_payload || {}, null, 2);
  renderDatasetValidation(example.validation);
}

function renderDatasetValidation(validation) {
  if (!els.datasetValidation) return;
  if (!validation) {
    els.datasetValidation.textContent = "";
    els.datasetValidation.dataset.state = "";
    return;
  }
  const pieces = [];
  pieces.push(validation.valid ? "valid" : "invalid");
  if (validation.missing_required_keys?.length) {
    pieces.push(`missing: ${validation.missing_required_keys.join(", ")}`);
  }
  if (validation.process_trace_errors?.length) {
    pieces.push(`trace: ${validation.process_trace_errors.join(", ")}`);
  }
  if (validation.invalid_constants?.length) {
    pieces.push(`constants: ${validation.invalid_constants.join(", ")}`);
  }
  if (validation.warnings?.length) {
    pieces.push(`warnings: ${validation.warnings.join(", ")}`);
  }
  els.datasetValidation.textContent = pieces.join(" · ");
  els.datasetValidation.dataset.state = validation.valid ? "ok" : "bad";
}

async function saveDatasetExample(statusOverride = null) {
  const example = state.activeDatasetExample;
  if (!example || !state.activeDatasetId) return;
  let assistantPayload;
  try {
    assistantPayload = JSON.parse(els.datasetJsonEditor.value || "{}");
  } catch (error) {
    els.datasetValidation.textContent = `JSON parse error: ${error.message}`;
    els.datasetValidation.dataset.state = "bad";
    return;
  }
  const body = {
    status: statusOverride || els.datasetStatusSelect.value,
    split: els.datasetSplitSelect.value || null,
    reviewer: els.datasetReviewer.value,
    review_notes: els.datasetNotes.value,
    assistant_payload: assistantPayload,
  };
  const data = await apiJson(
    `/api/datasets/${encodeURIComponent(state.activeDatasetId)}/examples/${encodeURIComponent(example.example_id)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  state.activeDatasetExample = { ...data.example, scenario: example.scenario, validation: data.validation };
  const index = state.datasetExamples.findIndex((item) => item.example_id === example.example_id);
  if (index >= 0) {
    state.datasetExamples[index] = {
      ...state.datasetExamples[index],
      status: data.example.status,
      split: data.example.split,
      review_notes: data.example.review_notes,
      updated_at: data.example.updated_at,
      valid: data.validation.valid,
      warnings: data.validation.warnings,
      missing_required_keys: data.validation.missing_required_keys,
      process_trace_errors: data.validation.process_trace_errors,
      invalid_constants: data.validation.invalid_constants,
    };
  }
  renderDatasetPanel();
}

async function validateActiveDataset() {
  if (!state.activeDatasetId) return;
  const data = await apiJson(`/api/datasets/${encodeURIComponent(state.activeDatasetId)}/validate`, {
    method: "POST",
  });
  renderDatasetSummary({ validation: data });
  await loadDatasetDetail(state.activeDatasetId);
}

async function exportActiveDataset() {
  if (!state.activeDatasetId) return;
  const data = await apiJson(`/api/datasets/${encodeURIComponent(state.activeDatasetId)}/export`, {
    method: "POST",
  });
  const counts = data.export?.counts || {};
  els.datasetValidation.textContent = `exported train=${counts.train || 0} validation=${counts.validation || 0} test=${counts.test || 0}`;
  els.datasetValidation.dataset.state = "ok";
  await loadDatasetDetail(state.activeDatasetId);
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
      parsed: null,
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
      parsed: event.parsed || null,
      status: event.status || "done",
      meta: event.error || metaFromOutput(event),
    };
    if (event.parsed) {
      state.parsed[target] = event.parsed;
    } else {
      delete state.parsed[target];
    }
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
els.refreshDatasetsBtn.addEventListener("click", loadDatasets);
els.datasetSelect.addEventListener("change", async () => {
  state.activeDatasetId = els.datasetSelect.value;
  state.activeDatasetExample = null;
  if (state.activeDatasetId) await loadDatasetDetail(state.activeDatasetId);
});
els.datasetTargetFilter.addEventListener("change", renderDatasetPanel);
els.datasetStatusFilter.addEventListener("change", renderDatasetPanel);
els.datasetProfileFilter.addEventListener("change", renderDatasetPanel);
els.validateDatasetBtn.addEventListener("click", validateActiveDataset);
els.exportDatasetBtn.addEventListener("click", exportActiveDataset);
els.saveDatasetExampleBtn.addEventListener("click", () => saveDatasetExample());
document.querySelectorAll("[data-dataset-status]").forEach((button) => {
  button.addEventListener("click", () => saveDatasetExample(button.dataset.datasetStatus));
});
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
