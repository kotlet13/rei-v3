const state = {
  bootstrap: null,
  result: null,
  activePanel: "native",
  busy: false,
};

const els = {
  statusDot: document.querySelector("#statusDot"),
  runtimeStatus: document.querySelector("#runtimeStatus"),
  runtimeMeta: document.querySelector("#runtimeMeta"),
  sceneSummary: document.querySelector("#sceneSummary"),
  sceneId: document.querySelector("#sceneId"),
  runId: document.querySelector("#runId"),
  invariantState: document.querySelector("#invariantState"),
  profileSelect: document.querySelector("#profileSelect"),
  debugToggle: document.querySelector("#debugToggle"),
  runCycleBtn: document.querySelector("#runCycleBtn"),
  tabs: [...document.querySelectorAll("[role='tab']")],
  panels: {
    native: document.querySelector("#panel-native"),
    communication: document.querySelector("#panel-communication"),
    character: document.querySelector("#panel-character"),
    ego: document.querySelector("#panel-ego"),
  },
};

const BODY_DIMENSIONS = [
  "energy",
  "fatigue",
  "pain",
  "arousal",
  "tension",
  "physical_integrity",
  "uncertainty",
  "trust",
  "attachment_security",
  "resource_security",
  "boundary_integrity",
  "escape_availability",
  "predictability",
];

function element(tag, className = "", text = null) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== null && text !== undefined) node.textContent = String(text);
  return node;
}

function append(parent, ...children) {
  for (const child of children.flat()) {
    if (child !== null && child !== undefined) parent.append(child);
  }
  return parent;
}

function asArray(value) {
  if (Array.isArray(value)) return value;
  if (value === null || value === undefined || value === "") return [];
  return [value];
}

function humanize(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function display(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (Array.isArray(value)) return value.length ? value.join(" · ") : "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function compactId(value) {
  const text = display(value);
  if (text.length <= 34) return text;
  return `${text.slice(0, 18)}…${text.slice(-10)}`;
}

function setRuntime(status, meta, mode = "idle") {
  els.runtimeStatus.textContent = status;
  els.runtimeMeta.textContent = meta;
  els.statusDot.dataset.state = mode;
}

async function apiJson(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "object" ? payload.detail || JSON.stringify(payload) : payload;
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return payload;
}

function panelHeading(title, description, meta = "") {
  const wrapper = element("div", "panel-heading");
  const copy = element("div");
  append(copy, element("h2", "", title), element("p", "", description));
  append(wrapper, copy);
  if (meta) append(wrapper, element("span", "meta-chip", meta));
  return wrapper;
}

function chips(values, emptyText = "None recorded") {
  const list = element("div", "chip-list");
  const items = asArray(values);
  if (!items.length) {
    append(list, element("span", "signal-chip", emptyText));
    return list;
  }
  for (const value of items) append(list, element("span", "signal-chip", display(value)));
  return list;
}

function fieldGroup(label, value, { asChips = false } = {}) {
  const group = element("div", "field-group");
  append(group, element("h4", "", label));
  append(group, asChips ? chips(value) : element("p", "", display(value)));
  return group;
}

function choiceLine(label, value) {
  const line = element("div", "choice-line");
  append(line, element("span", "", label), element("strong", "", display(value)));
  return line;
}

function keyValues(entries) {
  const list = element("dl", "kv-list");
  for (const [label, value] of entries) {
    const row = element("div", "kv-row");
    append(row, element("dt", "", label), element("dd", "", display(value)));
    append(list, row);
  }
  return list;
}

function rawDetails(label, payload) {
  const details = element("details", "raw-details");
  const summary = element("summary", "", label);
  const pre = element("pre", "raw-json", JSON.stringify(payload, null, 2));
  append(details, summary, pre);
  return details;
}

function card(title, payload = null) {
  const wrapper = element("article", "card");
  append(wrapper, element("h3", "", title));
  if (payload !== null) append(wrapper, rawDetails("Inspect exact artifact", payload));
  return wrapper;
}

function mindCard(title, letter, className, conclusion, groups) {
  const wrapper = element("article", `mind-card ${className}`);
  const heading = element("div", "mind-heading");
  append(heading, element("h3", "", title), element("span", "mind-badge", letter));
  append(wrapper, heading, choiceLine("Native option", conclusion?.option_id));
  for (const group of groups) append(wrapper, group);
  append(wrapper, rawDetails("Inspect native conclusion", conclusion));
  return wrapper;
}

function renderNativePanel(payload) {
  const panel = els.panels.native;
  panel.replaceChildren();
  const native = payload || {};
  const racio = native.racio || {};
  const emocio = native.emocio || {};
  const instinkt = native.instinkt || {};
  const eConclusion = emocio.conclusion || {};
  const iConclusion = instinkt.conclusion || {};
  const visualState = emocio.visual_state || {};

  append(
    panel,
    panelHeading(
      "Native layer",
      "Three modality-specific conclusions, frozen before character authority or communication.",
      state.result?.run?.profile_id || ""
    )
  );

  const grid = element("div", "mind-grid");
  append(
    grid,
    mindCard("Racio", "R", "racio", racio, [
      fieldGroup("Facts used", racio.facts_used, { asChips: true }),
      fieldGroup("Unknowns", racio.unknowns, { asChips: true }),
      fieldGroup("Causal sequence", racio.causal_sequence, { asChips: true }),
      fieldGroup("Utility structure", racio.utility_structure),
      fieldGroup("Main objection", racio.main_objection),
    ]),
    mindCard("Emocio", "E", "emocio", eConclusion, [
      fieldGroup("Desired transformation", eConclusion.desired_transformation),
      fieldGroup("Main obstacle", eConclusion.main_obstacle),
      fieldGroup("Action tendency", eConclusion.action_tendency),
      fieldGroup("Valuation dimensions", eConclusion.valuation_dimensions, { asChips: true }),
      fieldGroup("Intensity / uncertainty", [eConclusion.intensity, eConclusion.uncertainty], {
        asChips: true,
      }),
    ]),
    mindCard("Instinkt", "I", "instinkt", iConclusion, [
      fieldGroup("Dominant alarm", iConclusion.dominant_alarm),
      fieldGroup("Minimum safety condition", iConclusion.minimum_safety_condition),
      fieldGroup("Protected targets", iConclusion.protected_targets, { asChips: true }),
      fieldGroup("Action tendency", iConclusion.action_tendency),
      fieldGroup("Danger claims", iConclusion.danger_claims, { asChips: true }),
    ])
  );
  append(panel, grid);

  const imageSlots = asArray(emocio.image_slots);
  const imageTitle = element("div", "subsection-title");
  append(
    imageTitle,
    element("h3", "", "Emocio visual scenes"),
    element(
      "span",
      "",
      imageSlots.some((slot) => slot.status === "available")
        ? "Verified rendered artifacts"
        : "Renderer disabled · structured scenes remain authoritative"
    )
  );
  const imageSection = element("div", "subsection");
  const sceneGrid = element("div", "scene-grid");
  const valuationsByScene = new Map(
    asArray(visualState.option_valuations).map((valuation) => [valuation.rollout_scene_id, valuation])
  );
  for (const slot of imageSlots) {
    append(sceneGrid, renderSceneSlot(slot, valuationsByScene.get(slot.scene_id)));
  }
  append(imageSection, imageTitle, sceneGrid, rawDetails("Inspect exact Emocio visual state", visualState));
  append(panel, imageSection);

  const trajectorySection = element("div", "subsection");
  const trajectoryTitle = element("div", "subsection-title");
  append(
    trajectoryTitle,
    element("h3", "", "Instinkt body trajectories"),
    element("span", "", `${asArray(instinkt.rollouts).length} option rollouts · 13 body dimensions`)
  );
  append(trajectorySection, trajectoryTitle);
  for (const rollout of asArray(instinkt.rollouts)) append(trajectorySection, renderRollout(rollout));
  append(panel, trajectorySection);
}

function renderSceneSlot(slot, valuation = null) {
  const scene = slot.scene || slot.source_spec || {};
  const wrapper = element("article", "scene-card");
  const well = element("div", "image-well");
  if (slot.status === "available" && slot.url) {
    const image = element("img");
    image.src = slot.url;
    image.alt = `${humanize(scene.scene_kind || slot.scene_kind)} Emocio scene`;
    image.loading = "lazy";
    append(well, image);
  } else {
    const placeholder = element("div", "image-placeholder");
    append(
      placeholder,
      element("strong", "", "No rendered image artifact"),
      element("span", "", "The structured visual scene is available without invented pixels.")
    );
    append(well, placeholder);
  }
  const body = element("div", "scene-body");
  append(
    body,
    element("h4", "", humanize(scene.scene_kind || slot.scene_kind || "visual scene")),
    element("p", "", asArray(scene.composition).join(" · ") || compactId(slot.scene_id)),
    element("span", "image-status", humanize(slot.status || "not rendered"))
  );
  if (valuation) {
    const dimensions = asArray(valuation.dimensions).map(
      (dimension) => `${humanize(dimension.name)} ${display(dimension.score)}`
    );
    append(body, fieldGroup("Option valuation", dimensions, { asChips: true }));
  }
  append(wrapper, well, body);
  return wrapper;
}

function renderRollout(rollout) {
  const wrapper = element("details", "card body-trajectory");
  wrapper.open = rollout.option_id === state.result?.panels?.native?.instinkt?.conclusion?.option_id;
  const summary = element(
    "summary",
    "",
    `${rollout.option_id || "option"} · loss ${display(rollout.predicted_loss)} · recovery ${display(rollout.recoverability)}`
  );
  append(wrapper, summary);
  append(
    wrapper,
    keyValues([
      ["Alarm", rollout.dominant_alarm],
      ["Boundary", rollout.boundary_outcome],
      ["Trust", rollout.trust_outcome],
      ["Attachment", rollout.attachment_outcome],
      ["Escape", rollout.escape_outcome],
    ])
  );
  asArray(rollout.trajectory).forEach((bodyState, index) => {
    const step = element("div", "trajectory-step");
    append(step, element("div", "step-label", index === 0 ? "body before" : `step ${index}`));
    const bars = element("div", "body-bars");
    for (const dimension of BODY_DIMENSIONS) {
      const raw = Number(bodyState?.[dimension]);
      const value = Number.isFinite(raw) ? Math.max(0, Math.min(1, raw)) : 0;
      const row = element("div", "body-bar");
      const track = element("span", "bar-track");
      const fill = element("span", "bar-fill");
      fill.style.width = `${value * 100}%`;
      append(track, fill);
      append(row, element("span", "", humanize(dimension)), track, element("output", "", display(raw)));
      append(bars, row);
    }
    append(step, bars);
    append(wrapper, step);
  });
  append(wrapper, rawDetails("Inspect exact rollout", rollout));
  return wrapper;
}

function byMind(items, mind, index) {
  if (items && !Array.isArray(items) && typeof items === "object") {
    const named = items[mind === "E" ? "emocio" : "instinkt"];
    if (named) return named;
  }
  return asArray(items).find((item) => item?.source_mind === mind || item?.mind === mind) || asArray(items)[index] || {};
}

function renderCommunicationPanel(payload) {
  const panel = els.panels.communication;
  panel.replaceChildren();
  const communication = payload || {};
  append(
    panel,
    panelHeading(
      "Communication layer",
      "Observable manifestation is separated from Racio’s fallible interpretation.",
      communication.ground_truth_visible ? "debug visible" : "runtime view"
    )
  );

  const warning = element("div", "warning-banner");
  append(
    warning,
    element("strong", "", "Epistemic boundary"),
    document.createTextNode(
      communication.warning ||
        "Racio receives manifestations only. Native Emocio and Instinkt conclusions are never supplied as runtime ground truth."
    )
  );
  append(panel, warning);

  if (communication.evaluator_ground_truth) {
    const banner = element("div", "debug-banner");
    append(
      banner,
      element("strong", "", "DEBUG / EVALUATOR GROUND TRUTH"),
      document.createTextNode(
        "This comparison exists for evaluation only. Racio did not see these native motives or option IDs."
      )
    );
    append(panel, banner);
  }

  const comparison = element("div", "comparison-grid");
  for (const [mind, index, label] of [
    ["E", 0, "Emocio"],
    ["I", 1, "Instinkt"],
  ]) {
    const manifestation = byMind(communication.manifestations, mind, index);
    const interpretation = byMind(communication.interpretations, mind, index);
    const gap = byMind(communication.translation_gaps, mind, index);
    append(comparison, renderCommunicationFlow(label, mind, manifestation, interpretation, gap));
  }
  append(panel, comparison);

  if (communication.evaluator_ground_truth) {
    const debugSection = element("div", "subsection");
    const title = element("div", "subsection-title");
    append(title, element("h3", "", "Evaluator-only native comparison"), element("span", "", "never an interpreter input"));
    const debugGrid = element("div", "panel-grid two");
    const truth = communication.evaluator_ground_truth;
    for (const key of ["emocio", "instinkt"]) {
      const value = truth[key];
      if (!value) continue;
      const truthCard = card(humanize(key));
      append(
        truthCard,
        choiceLine("Native option", value?.native_option_id),
        fieldGroup("Native action tendency", value?.native_action_tendency),
        fieldGroup(
          "Native motive",
          value?.native_motive_summary || value?.desired_transformation || value?.minimum_safety_condition
        ),
        rawDetails("Inspect evaluator truth", value)
      );
      append(debugGrid, truthCard);
    }
    append(debugSection, title, debugGrid);
    append(panel, debugSection);
  }
}

function renderCommunicationFlow(label, mind, manifestation, interpretation, gap) {
  const wrapper = element("article", `mind-card ${mind === "E" ? "emocio" : "instinkt"}`);
  const heading = element("div", "mind-heading");
  append(heading, element("h3", "", label), element("span", "mind-badge", mind));
  append(wrapper, heading);

  const flow = element("div", "flow-column");
  const manifested = card("Manifestation");
  const manifestationFields = Object.entries(manifestation || {})
    .filter(([key, value]) => typeof value !== "object" && !key.includes("hash") && !key.includes("id") && key !== "schema_version")
    .slice(0, 8)
    .map(([key, value]) => [humanize(key), value]);
  append(manifested, keyValues(manifestationFields), rawDetails("Exact manifestation", manifestation));
  const interpreted = card("Racio interpretation");
  append(
    interpreted,
    keyValues([
      ["Inferred tendency", interpretation?.inferred_action_tendency],
      ["Inferred option", interpretation?.inferred_option_id],
      ["Confidence", interpretation?.confidence],
      ["Policy", interpretation?.interpreter_policy],
    ]),
    fieldGroup("Inferred motive", interpretation?.inferred_motive),
    rawDetails("Exact interpretation", interpretation)
  );
  append(flow, manifested, element("div", "flow-arrow", "→"), interpreted);
  append(wrapper, flow);

  const gapBox = element("div", "translation-gap");
  append(
    gapBox,
    element("strong", "", `Translation gap · ${humanize(gap?.distortion_type || "not measured")}`),
    element(
      "p",
      "",
      `Motive fidelity ${display(gap?.motive_fidelity)} · option match ${display(gap?.option_match)} · status ${display(gap?.gap_status)}`
    )
  );
  append(wrapper, gapBox, rawDetails("Inspect safe gap summary", gap));
  return wrapper;
}

function renderCharacterPanel(payload) {
  const panel = els.panels.character;
  panel.replaceChildren();
  const character = payload || {};
  const structural = character.structural_profile || {};
  const effective = character.effective_authority || {};
  const mandate = character.governance_mandate || {};
  const decision = character.conscious_decision || {};
  const behavior = character.behavior_resultant || {};

  append(
    panel,
    panelHeading(
      "Character authority",
      "Stable structure selects governance; Racio commits consciously; behavior remains a separate resultant.",
      structural.profile_id || ""
    )
  );

  const overview = element("div", "panel-grid two");
  const authorityCard = card("Structural and effective authority");
  append(authorityCard, choiceLine("Profile", structural.profile_id));
  const tiers = element("div", "authority-tiers");
  asArray(structural.authority_tiers || character.authority_tiers).forEach((tier, index, all) => {
    append(tiers, element("span", "tier", asArray(tier).join(" = ")));
    if (index < all.length - 1) append(tiers, element("span", "tier-arrow", ">"));
  });
  const authorityHeading = element("div", "field-group");
  append(authorityHeading, element("h4", "", "Authority tiers"), tiers);
  append(
    authorityCard,
    authorityHeading,
    fieldGroup("Effective tiers", asArray(effective.effective_tiers).map((tier) => asArray(tier).join(" = ")), {
      asChips: true,
    }),
    rawDetails("Inspect authority", { structural, effective })
  );

  const availabilityCard = card("Processor availability");
  const availability = character.processor_availability || {};
  const availabilityScores = availability.scores || {};
  const unavailable = new Set(asArray(availability.unavailable_minds));
  const availabilityList = element("div", "availability-list");
  for (const mind of ["R", "E", "I"]) {
    const row = element("div", "availability-row");
    const value =
      availability.explicit && Object.hasOwn(availabilityScores, mind)
        ? availabilityScores[mind]
        : unavailable.has(mind)
          ? "unavailable"
          : "retained · not explicitly measured";
    append(row, element("span", "", mind), element("output", "", display(value)));
    append(availabilityList, row);
  }
  append(
    availabilityCard,
    availabilityList,
    fieldGroup(
      "Availability basis",
      availability.status ||
        (effective.functional_override ? "explicit functional override" : "no explicit unavailability · all retained")
    ),
    rawDetails("Inspect availability evidence", effective.functional_override)
  );
  append(overview, authorityCard, availabilityCard);
  append(panel, overview);

  const governanceSection = element("div", "subsection");
  const governanceTitle = element("div", "subsection-title");
  append(governanceTitle, element("h3", "", "Governance resolution"), element("span", "", display(mandate.status)));
  const governanceGrid = element("div", "panel-grid two");
  const mandateCard = card("Mandate");
  append(
    mandateCard,
    choiceLine("Governed option", mandate.option_id),
    fieldGroup("Structural sources", mandate.structural_source_minds, { asChips: true }),
    fieldGroup("Objections", mandate.objections, { asChips: true }),
    fieldGroup("Delegation", character.delegation ? display(character.delegation) : "None"),
    rawDetails("Inspect mandate", mandate)
  );
  const conflictCard = card("Conflict and majority");
  const majority = character.thirteenth_majority || {};
  const agreeingMinds = asArray(majority.agreeing_minds);
  const majoritySummary = majority.applicable
    ? `${display(majority.winning_option_id)} · ${agreeingMinds.length}/3 (${agreeingMinds.join(", ")})`
    : "not applicable";
  append(
    conflictCard,
    keyValues([
      ["Pair conflict", character.pair_conflict ? "present" : "none"],
      ["13th majority", majoritySummary],
    ]),
    rawDetails("Inspect pair conflict", character.pair_conflict),
    rawDetails("Inspect 13th majority", character.thirteenth_majority)
  );
  append(governanceGrid, mandateCard, conflictCard);
  append(governanceSection, governanceTitle, governanceGrid);
  append(panel, governanceSection);

  const chainSection = element("div", "subsection");
  const chainTitle = element("div", "subsection-title");
  append(chainTitle, element("h3", "", "Mandate → conscious decision → behavior"), element("span", "", "three distinct records"));
  const chain = element("div", "decision-chain");
  for (const [label, item, option, status] of [
    ["Governance mandate", mandate, mandate.option_id, mandate.status],
    ["Conscious decision", decision, decision.option_id, decision.decision_status],
    ["Behavior resultant", behavior, behavior.option_id, behavior.status],
  ]) {
    const node = element("article", "decision-node");
    append(node, element("span", "", label), element("strong", "", display(option)), element("p", "", humanize(status)));
    append(node, rawDetails(`Inspect ${label.toLowerCase()}`, item));
    append(chain, node);
  }
  append(chainSection, chainTitle, chain);
  append(panel, chainSection);
}

function renderEgoPanel(payload) {
  const panel = els.panels.ego;
  panel.replaceChildren();
  const ego = payload || {};
  const snapshot = ego.composition_snapshot || {};
  const measure = ego.measure || {};
  const narrative = ego.self_narrative || {};
  const projections = ego.projections || {};

  append(
    panel,
    panelHeading(
      "Ego composition",
      "Executed history becomes sourced motifs, unresolved tensions, insights, and modality-specific projections.",
      compactId(snapshot.snapshot_id)
    )
  );

  const upper = element("div", "ego-grid");
  const timelineCard = card("EgoTrace timeline");
  const timeline = element("div", "trace-timeline");
  for (const event of asArray(ego.timeline)) {
    const node = element("div", "trace-node");
    append(
      node,
      element("strong", "", humanize(event.event_kind || event.kind || "measure")),
      element("code", "", compactId(event.event_id || event.measure_id || event.id))
    );
    append(timeline, node);
  }
  append(
    timelineCard,
    choiceLine("Current measure", measure.measure_id),
    timeline,
    rawDetails("Inspect EgoMeasure", measure)
  );

  const compositionCard = card("Composition snapshot");
  append(
    compositionCard,
    fieldGroup("Identity motifs", snapshot.identity_motifs, { asChips: true }),
    fieldGroup("Recurring conflicts", snapshot.recurring_conflicts, { asChips: true }),
    fieldGroup("Translation errors", snapshot.recurring_translation_errors, { asChips: true }),
    fieldGroup("Unresolved tensions", snapshot.unresolved_tensions, { asChips: true }),
    fieldGroup("Resolved tensions", snapshot.resolved_tensions, { asChips: true }),
    rawDetails("Inspect composition snapshot", snapshot)
  );
  append(upper, timelineCard, compositionCard);
  append(panel, upper);

  const insightSection = element("div", "subsection");
  const insightTitle = element("div", "subsection-title");
  append(insightTitle, element("h3", "", "Spoznanja and self-narrative"), element("span", "", "hypothesis vs trace-derived composition"));
  const insightGrid = element("div", "panel-grid two");
  const insightsCard = card("Trace-backed spoznanja");
  const insightList = element("div", "insight-list");
  for (const insight of asArray(snapshot.spoznanja)) append(insightList, element("div", "insight", display(insight)));
  if (!asArray(snapshot.spoznanja).length) append(insightList, element("div", "insight", "No spoznanje recorded"));
  append(insightsCard, insightList, rawDetails("Inspect sourced claims", snapshot.sourced_claims));
  const narrativeCard = card("Racio self-narrative");
  append(
    narrativeCard,
    fieldGroup("Claimed motive", narrative.claimed_motive),
    fieldGroup("Explanation", narrative.explanation),
    fieldGroup("Acknowledged minds", narrative.acknowledged_minds, { asChips: true }),
    fieldGroup("Omitted minds", narrative.omitted_minds, { asChips: true }),
    rawDetails("Inspect self-narrative", narrative)
  );
  append(insightGrid, insightsCard, narrativeCard);
  append(insightSection, insightTitle, insightGrid);
  append(panel, insightSection);

  const projectionSection = element("div", "subsection");
  const projectionTitle = element("div", "subsection-title");
  append(projectionTitle, element("h3", "", "Three projected histories"), element("span", "", "same trace · modality-specific memory"));
  const projectionGrid = element("div", "projection-grid");
  append(
    projectionGrid,
    renderProjection("Racio projection", "racio", projections.racio, ["facts", "chronology", "causal_links", "commitments"]),
    renderProjection("Emocio projection", "emocio", projections.emocio, ["recurring_scenes", "desire_motifs", "rupture_motifs", "belonging_motifs"]),
    renderProjection("Instinkt projection", "instinkt", projections.instinkt, ["dangers", "losses", "recovery_patterns", "boundary_patterns", "trust_patterns"])
  );
  append(projectionSection, projectionTitle, projectionGrid);
  append(panel, projectionSection);
}

function renderProjection(title, className, projection = {}, fields = []) {
  const wrapper = element("article", `projection-card ${className}`);
  append(wrapper, element("h3", "", title), choiceLine("Projection ID", compactId(projection?.projection_id)));
  for (const field of fields) append(wrapper, fieldGroup(humanize(field), projection?.[field], { asChips: true }));
  append(wrapper, rawDetails("Inspect exact projection", projection));
  return wrapper;
}

function renderAll() {
  if (!state.result) return;
  const panels = state.result.panels || {};
  renderNativePanel(panels.native);
  renderCommunicationPanel(panels.communication);
  renderCharacterPanel(panels.character);
  renderEgoPanel(panels.ego);

  const run = state.result.run || {};
  els.runId.textContent = `run ${compactId(run.run_id)}`;
  const passed = Boolean(run.all_invariants_passed ?? state.result.diagnostics?.invariants?.all_passed);
  els.invariantState.textContent = passed ? "all invariants passed" : "invariant failure";
  els.invariantState.dataset.state = passed ? "ok" : "bad";
}

function activatePanel(name, { focus = false } = {}) {
  if (!els.panels[name]) return;
  state.activePanel = name;
  for (const tab of els.tabs) {
    const active = tab.dataset.panel === name;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
    if (active && focus) tab.focus();
  }
  for (const [panelName, panel] of Object.entries(els.panels)) {
    const active = panelName === name;
    panel.hidden = !active;
    panel.classList.toggle("active", active);
  }
}

function profileContracts() {
  return state.bootstrap?.profile_contracts || state.bootstrap?.profiles || [];
}

function templateRequest() {
  return state.bootstrap?.request || state.bootstrap?.default_request || state.bootstrap?.fixture;
}

function buildCycleRequest() {
  const template = templateRequest();
  if (!template) throw new Error("Bootstrap did not provide a deterministic request fixture.");
  const request = structuredClone(template);
  const token = `${Date.now().toString(36)}-${crypto.randomUUID().replaceAll("-", "").slice(0, 8)}`.toLowerCase();
  request.run_id = `gui-${token}`;
  request.ego_id = `gui-ego-${token}`;
  request.started_at = new Date().toISOString();

  const profileId = els.profileSelect.value;
  const contract = profileContracts().find((item) => (typeof item === "string" ? item : item.profile_id) === profileId);
  if (contract && typeof contract === "object") {
    request.character = {
      ...request.character,
      profile_id: contract.profile_id,
      authority_tiers: contract.authority_tiers,
      rule: contract.rule,
    };
  }
  return request;
}

async function runCycle() {
  if (state.busy) return;
  state.busy = true;
  els.runCycleBtn.disabled = true;
  els.profileSelect.disabled = true;
  setRuntime("Running native cycle…", "Deterministic R/E/I providers · CPU only", "working");
  try {
    const request = buildCycleRequest();
    const debug = els.debugToggle.checked ? "true" : "false";
    state.result = await apiJson(`/api/cycles?debug=${debug}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    renderAll();
    setRuntime(
      "Cycle complete",
      `${state.result.run?.profile_id || request.character.profile_id} · ${state.result.run?.run_id || request.run_id}`,
      "ok"
    );
  } catch (error) {
    console.error(error);
    setRuntime("Cycle failed", error.message, "error");
    const active = els.panels[state.activePanel];
    const errorCard = element("div", "error-card");
    append(errorCard, element("h2", "", "Workbench request failed"), element("p", "", error.message));
    active.replaceChildren(errorCard);
  } finally {
    state.busy = false;
    els.runCycleBtn.disabled = false;
    els.profileSelect.disabled = false;
  }
}

function loadProfiles() {
  els.profileSelect.replaceChildren();
  for (const item of profileContracts()) {
    const profileId = typeof item === "string" ? item : item.profile_id;
    const option = element("option", "", profileId);
    option.value = profileId;
    if (profileId === templateRequest()?.character?.profile_id) option.selected = true;
    append(els.profileSelect, option);
  }
  els.profileSelect.disabled = false;
}

async function bootstrap() {
  try {
    state.bootstrap = await apiJson("/api/bootstrap");
    const request = templateRequest();
    if (!request) throw new Error("Missing deterministic request fixture.");
    loadProfiles();
    els.sceneSummary.textContent = request.scene?.raw_input || "Deterministic native cycle";
    els.sceneId.textContent = `scene ${compactId(request.scene?.event_id)}`;
    els.runCycleBtn.disabled = false;
    setRuntime(
      "Ready",
      "Checked-in fixture · deterministic providers · no model or renderer",
      "ok"
    );
  } catch (error) {
    console.error(error);
    setRuntime("Bootstrap failed", error.message, "error");
    els.sceneSummary.textContent = error.message;
  }
}

for (const tab of els.tabs) {
  tab.addEventListener("click", () => activatePanel(tab.dataset.panel));
  tab.addEventListener("keydown", (event) => {
    const current = els.tabs.indexOf(tab);
    let next = null;
    if (event.key === "ArrowRight") next = (current + 1) % els.tabs.length;
    if (event.key === "ArrowLeft") next = (current - 1 + els.tabs.length) % els.tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = els.tabs.length - 1;
    if (next !== null) {
      event.preventDefault();
      activatePanel(els.tabs[next].dataset.panel, { focus: true });
    }
  });
}

els.runCycleBtn.addEventListener("click", runCycle);
activatePanel("native");
bootstrap();
