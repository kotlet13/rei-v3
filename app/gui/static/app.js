const RACIO_GROUND_TRUTH_WARNING = "Racio did not receive evaluator ground truth.";

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

const state = {
  bootstrap: null,
  lab: null,
  labError: null,
  shadowRegistry: null,
  shadowRegistryError: null,
  shadowEvidence: null,
  shadowEvidenceError: null,
  selectedShadowEvidenceId: "en1-runtime",
  selectedShadowMind: "E",
  shadowBusy: false,
  shadowRequestGeneration: 0,
  shadowAbortController: null,
  result: null,
  activePanel: "semantic",
  busy: false,
  sessionEgoId: `gui-ego-${randomToken()}`,
  selectedFamilyId: null,
  selectedVariantId: null,
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
    semantic: document.querySelector("#panel-semantic"),
    racio: document.querySelector("#panel-racio"),
    emocio: document.querySelector("#panel-emocio"),
    instinkt: document.querySelector("#panel-instinkt"),
    character: document.querySelector("#panel-character"),
    ego: document.querySelector("#panel-ego"),
  },
};

function randomToken() {
  const uuid = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
  return `${Date.now().toString(36)}-${uuid.replaceAll("-", "").replaceAll(".", "").slice(0, 10)}`.toLowerCase();
}

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
}

function asArray(value) {
  if (Array.isArray(value)) return value;
  if (value === null || value === undefined || value === "") return [];
  return [value];
}

function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function humanize(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function englishRuntimeValue(value) {
  if (Array.isArray(value)) return value.map(englishRuntimeValue);
  if (typeof value !== "string") return value;
  return value
    .replaceAll("simulated_spoznanje", "simulated realization")
    .replaceAll("no_spoznanje", "no realization")
    .replaceAll("spoznanje", "realization");
}

function display(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (Array.isArray(value)) return value.length ? value.map(display).join(" · ") : "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function compactId(value) {
  const text = display(value);
  if (text.length <= 40) return text;
  return `${text.slice(0, 22)}…${text.slice(-12)}`;
}

function statusTone(value) {
  const normalized = String(value ?? "").toLowerCase();
  if (["true", "pass", "passed", "available", "canon_approved", "ok", "selected"].includes(normalized)) return "ok";
  if (["false", "fail", "failed", "error", "rejected"].includes(normalized)) return "bad";
  if (["blocked", "warning", "observed", "not_measured", "not_executed", "not_executed_in_this_cycle"].includes(normalized)) return "warn";
  return "neutral";
}

function statusPill(label, value) {
  const pill = element("span", "status-pill", `${label}: ${display(value)}`);
  pill.dataset.state = statusTone(value);
  return pill;
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

function safeTranslationGap(gap) {
  const source = asObject(gap);
  return {
    translation_gap_id: source.translation_gap_id,
    source_mind: source.source_mind,
    interpretation_id: source.interpretation_id,
    gap_status: source.gap_status,
    distortion_type: source.distortion_type,
    evaluator_detail_visible: false,
    detail: "Native comparison truth is available only through the local evaluator-debug switch.",
  };
}

function safeTranslationErrorText(value) {
  const parts = String(value || "").split(":");
  return parts.length >= 3 && parts[0] === "translation_gap"
    ? parts.slice(0, 3).join(":")
    : "translation_gap:detail_withheld";
}

function redactEvaluatorState(result = state.result) {
  const panels = asObject(result?.panels);
  const current = asObject(panels.racio);
  if (Object.keys(current).length) {
    const safe = { ...current };
    delete safe.evaluator_ground_truth;
    delete safe.translation_gaps;
    delete safe.evaluator_labels;
    safe.ground_truth_visible = false;
    safe.warning = state.bootstrap?.communication_warning || RACIO_GROUND_TRUTH_WARNING;
    panels.racio = safe;
  }

  const ego = asObject(panels.ego);
  if (Object.keys(ego).length) {
    const safeMeasure = (measure) => {
      const payload = { ...asObject(measure) };
      payload.translation_gaps = asArray(payload.translation_gaps).map(safeTranslationGap);
      return payload;
    };
    const snapshot = { ...asObject(ego.composition_snapshot) };
    snapshot.recurring_translation_errors = asArray(snapshot.recurring_translation_errors).map(safeTranslationErrorText);
    snapshot.sourced_claims = asArray(snapshot.sourced_claims).map((claim) => {
      const safeClaim = { ...asObject(claim) };
      if (safeClaim.kind === "recurring_translation_error") {
        safeClaim.text = safeTranslationErrorText(safeClaim.text);
        safeClaim.evaluator_detail_visible = false;
      }
      return safeClaim;
    });
    snapshot.translation_error_detail_visible = false;
    const narrative = { ...asObject(ego.self_narrative) };
    for (const fieldName of ["recurrent_translation_gaps", "recurring_translation_errors"]) {
      if (fieldName in narrative) narrative[fieldName] = asArray(narrative[fieldName]).map(safeTranslationErrorText);
    }
    if ("translation_gaps" in narrative) narrative.translation_gaps = asArray(narrative.translation_gaps).map(safeTranslationGap);
    panels.ego = {
      ...ego,
      measure: safeMeasure(ego.measure),
      timeline: asArray(ego.timeline).map((item) => (
        item?.event_kind === "measure"
          ? { ...item, event: safeMeasure(item.event) }
          : item
      )),
      composition_snapshot: snapshot,
      self_narrative: narrative,
    };
  }
  return result;
}

function panelHeading(title, description, meta = "") {
  const wrapper = element("div", "panel-heading");
  const copy = element("div");
  append(copy, element("h2", "", title), element("p", "", description));
  append(wrapper, copy);
  if (meta) append(wrapper, element("span", "meta-chip", meta));
  return wrapper;
}

function chips(values, emptyText = "None recorded", className = "") {
  const list = element("div", `chip-list ${className}`.trim());
  const items = asArray(values);
  if (!items.length) {
    append(list, element("span", "signal-chip empty", emptyText));
    return list;
  }
  for (const value of items) append(list, element("span", "signal-chip", display(value)));
  return list;
}

function fieldGroup(label, value, { asChips = false, emptyText = "None recorded" } = {}) {
  const group = element("div", "field-group");
  append(group, element("h4", "", label));
  append(group, asChips ? chips(value, emptyText) : element("p", "", display(value)));
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
  append(details, element("summary", "", label), element("pre", "raw-json", JSON.stringify(payload, null, 2)));
  return details;
}

function card(title, payload = null, className = "") {
  const wrapper = element("article", `card ${className}`.trim());
  append(wrapper, element("h3", "", title));
  if (payload !== null) append(wrapper, rawDetails("Inspect exact artifact", payload));
  return wrapper;
}

function emptyNotice(title, detail) {
  const notice = element("div", "empty-notice");
  append(notice, element("strong", "", title), element("p", "", detail));
  return notice;
}

function subsectionTitle(title, meta = "") {
  const heading = element("div", "subsection-title");
  append(heading, element("h3", "", title));
  if (meta) append(heading, element("span", "", meta));
  return heading;
}

function semanticFamilies() {
  const families = state.lab?.families;
  if (Array.isArray(families)) return families;
  if (families && typeof families === "object") return Object.values(families);
  return [];
}

function familyId(family) {
  return family?.family_id || family?.id || "unknown-family";
}

function semanticFamilyLabel(family) {
  return humanize(
    String(familyId(family))
      .replace(/^sf_/, "")
      .replace(/spoznanje/g, "realization")
  );
}

function semanticLanguageLabel(language) {
  if (language === "sl") return "Slovenian";
  if (language === "en") return "English";
  return humanize(language || "language not recorded");
}

function selectedVariantInputLabel(variant) {
  const language = semanticLanguageLabel(variant?.language);
  return `Selected research input — ${language}${variant?.language === "sl" ? " source evidence" : ""}`;
}

function semanticModeLabel(mode) {
  const labels = {
    sl_canonical: "Canonical source",
    sl_paraphrase: "Source paraphrase",
    en_operational_gloss: "Operational English gloss",
  };
  return labels[mode] || humanize(mode);
}

function familyVariants(family) {
  return asArray(family?.variants || family?.semantic_variants);
}

function sourceLocatorCard(locator, index) {
  const source = asObject(locator);
  const item = card(`Source ${index + 1}`);
  append(
    item,
    keyValues([
      ["Original source file", source.source_file || source.path],
      ["Source section title — original language", source.section],
      ["Page", source.page],
    ]),
    fieldGroup("Claim IDs", source.claim_ids, { asChips: true }),
    fieldGroup("Source excerpt summary — Slovenian", source.excerpt_summary_sl || source.summary_sl),
    rawDetails("Inspect source locator", source)
  );
  return item;
}

function routeItems(value) {
  const routeValue = value?.routes || value?.actual_routes || value?.expected_routes || value;
  return asArray(routeValue).map((route) => (typeof route === "string" ? { route_id: route } : asObject(route)));
}

function routeCard(title, routes, emptyText) {
  const wrapper = card(title, null, "route-card");
  const items = routeItems(routes);
  if (!items.length) {
    append(wrapper, emptyNotice(emptyText, "The workbench does not substitute expected truth for missing execution evidence."));
    return wrapper;
  }
  for (const route of items) {
    const item = element("div", "route-item");
    append(
      item,
      choiceLine("Route", route.route_id || route.candidate_route_id || route.id),
      choiceLine("Mind", route.mind || route.source_mind),
      choiceLine("Option", route.option_id || route.interpreted_option_id),
      fieldGroup("Route tags", route.route_tags || route.tags, { asChips: true }),
      fieldGroup("Evidence", route.evidence_ids || route.evidence_artifact_ids, { asChips: true }),
      fieldGroup(
        route.short_decision_bridge_sl
          ? "Source decision bridge — Slovenian"
          : "Source decisive representation — original language",
        route.short_decision_bridge_sl || route.decisive_representation
      ),
      rawDetails("Inspect route", route)
    );
    append(wrapper, item);
  }
  return wrapper;
}

function variantFailureTags(variant, family) {
  const evaluation = asObject(variant?.evaluation || variant?.evaluation_result);
  const issues = asArray(evaluation.issues || variant?.issues || family?.issues);
  return [
    ...asArray(variant?.failure_tags || variant?.issue_codes || evaluation.failure_tags || evaluation.issue_codes),
    ...issues.map((issue) => (typeof issue === "string" ? issue : issue.issue_code || issue.code || issue.tag)).filter(Boolean),
  ];
}

function variantActualRoutes(variant) {
  const evaluation = asObject(variant?.evaluation || variant?.evaluation_result);
  return (
    variant?.actual_routes ||
    variant?.candidate_routes ||
    evaluation.actual_routes ||
    evaluation.actual_route_ids ||
    evaluation.context?.actual_route_ids ||
    []
  );
}

function bilingualText(family, selectedVariant, language) {
  const sideBySide = asObject(selectedVariant?.side_by_side);
  const variants = familyVariants(family);
  const preferredMode = language === "sl" ? "sl_canonical" : "en_operational_gloss";
  const variant =
    variants.find((item) => item.language === language && item.mode === preferredMode) ||
    variants.find((item) => item.language === language);
  const bilingual = asObject(family?.bilingual_pair || family?.bilingual);
  return {
    variant,
    text:
      sideBySide[language] ||
      variant?.input_text ||
      variant?.text ||
      (language === "sl" ? bilingual.sl_text : bilingual.en_text) ||
      null,
  };
}

function renderBenchmarkStatus(benchmark) {
  const section = element("section", "subsection benchmark-section");
  append(section, subsectionTitle("Integrated benchmark status", "dimensions remain separate"));
  const technicalRecord = asObject(benchmark.technical);
  const researchRecord = asObject(benchmark.research);
  const authorityRecord = asObject(benchmark.authority);
  const modelCalls = asObject(benchmark.model_calls);
  const metricDisposition = asObject(benchmark.metric_disposition);
  const statuses = element("div", "benchmark-status-grid");
  const technical = technicalRecord.contract_passed ?? benchmark.technical_contract_passed ?? benchmark.technical_status;
  const research = researchRecord.quality_status ?? benchmark.research_quality_status ?? benchmark.research_status;
  const semanticAuthority = authorityRecord.semantic_granted ?? benchmark.semantic_authority_granted ?? benchmark.semantic_authority;
  const productionAuthority = authorityRecord.production_granted ?? benchmark.production_authority_granted ?? benchmark.production_authority;
  for (const [title, value, detail] of [
    ["Technical contract", technical, "Current deterministic and bounded contracts"],
    ["Research quality", research, "Model-backed and semantic readiness"],
    ["Semantic authority", semanticAuthority, "Permission to treat semantic output as authoritative"],
    ["Production authority", productionAuthority, "Permission for production visual influence"],
  ]) {
    const status = card(title, null, "benchmark-status-card");
    status.dataset.state = statusTone(value);
    append(status, element("strong", "benchmark-status-value", display(value)), element("p", "", detail));
    append(statuses, status);
  }
  append(section, statuses);

  const counts = element("div", "status-strip");
  for (const [label, value] of [
    ["passed metrics", metricDisposition.passed ?? benchmark.passed_metric_count],
    ["blocked metrics", metricDisposition.blocked ?? benchmark.blocked_metric_count],
    ["observed metrics", metricDisposition.observed ?? benchmark.observed_metric_count],
    ["not measured", metricDisposition.not_measured ?? benchmark.not_measured_metric_count],
    ["current model calls", modelCalls.current],
    ["historical model calls", modelCalls.historical],
  ]) {
    if (value !== undefined) append(counts, statusPill(label, value));
  }
  append(section, counts);

  const blockerRecords = asArray(researchRecord.blockers || benchmark.failures);
  const blockers =
    benchmark.research_readiness_blocker_codes ||
    benchmark.blocker_codes ||
    blockerRecords.map((item) => (typeof item === "string" ? item : item.code || item.blocker_code)).filter(Boolean);
  const blockerCard = card("Research-readiness blockers", null, "blocker-card");
  append(
    blockerCard,
    chips(blockers, "No blocker codes recorded", "failure-chips"),
    fieldGroup(
      "Score policy",
      benchmark.aggregate_score_present === false
        ? "No aggregate score. Every metric remains a separate dimension."
        : "No aggregate score is displayed by this workbench."
    )
  );
  for (const blocker of blockerRecords) {
    if (typeof blocker === "string") continue;
    const blockerDetail = element("div", "blocker-detail");
    append(
      blockerDetail,
      element("strong", "", blocker.code || blocker.blocker_code || "Unidentified blocker"),
      element("p", "", blocker.detail || "No detail recorded."),
      fieldGroup("Affected ablation families", blocker.affected_ablation_families, { asChips: true }),
      fieldGroup("Affected metric dimensions", blocker.affected_metric_dimensions, { asChips: true })
    );
    append(blockerCard, blockerDetail);
  }
  append(section, blockerCard);

  const metrics = asArray(benchmark.metrics);
  if (metrics.length) {
    const metricGrid = element("div", "metric-grid semantic-metrics");
    for (const metric of metrics) {
      const metricCard = card(humanize(metric.dimension), null, "metric-card");
      metricCard.dataset.state = statusTone(metric.status);
      append(
        metricCard,
        statusPill("status", metric.status),
        choiceLine("Value", metric.value),
        choiceLine("Evidence ratio", metric.numerator !== undefined ? `${metric.numerator}/${metric.denominator}` : null),
        fieldGroup("Blockers", metric.blocker_codes, { asChips: true }),
        fieldGroup("Limitation", metric.limitation),
        rawDetails("Inspect metric", metric)
      );
      append(metricGrid, metricCard);
    }
    append(section, metricGrid);
  }
  return section;
}

function renderSemanticFamily(family) {
  const section = element("section", "semantic-family");
  const variants = familyVariants(family);
  if (!state.selectedVariantId || !variants.some((item) => item.variant_id === state.selectedVariantId)) {
    state.selectedVariantId = variants[0]?.variant_id || null;
  }
  const variant = variants.find((item) => item.variant_id === state.selectedVariantId) || variants[0] || {};
  const evaluation = asObject(variant.evaluation || variant.evaluation_result);

  const controls = element("div", "lab-controls");
  const variantField = element("label", "field lab-field");
  append(variantField, element("span", "", "Test variant"));
  const variantSelect = element("select", "lab-select");
  variantSelect.setAttribute("aria-label", "Semantic variant");
  for (const item of variants) {
    const option = element(
      "option",
      "",
      `${semanticModeLabel(item.mode || item.language)} · ${semanticLanguageLabel(item.language)}`
    );
    option.value = item.variant_id;
    option.selected = item.variant_id === state.selectedVariantId;
    append(variantSelect, option);
  }
  variantSelect.addEventListener("change", () => {
    state.selectedVariantId = variantSelect.value;
    renderSemanticPanel({ focusControl: "variant" });
  });
  append(variantField, variantSelect);
  append(
    controls,
    variantField,
    statusPill("family review", family.reviewer_status),
    statusPill("variant review", variant.reviewer_status)
  );
  append(section, controls);

  const selectedVariantCard = card("Selected test variant", null, "selected-variant-card");
  selectedVariantCard.dataset.variantId = variant.variant_id || "unknown-variant";
  append(
    selectedVariantCard,
    keyValues([
      ["Mode", semanticModeLabel(variant.mode || variant.language)],
      ["Language", semanticLanguageLabel(variant.language)],
      ["Variant ID", variant.variant_id],
    ]),
    fieldGroup(selectedVariantInputLabel(variant), variant.input_text),
    fieldGroup("Recorded perturbation", variant.perturbation),
    rawDetails("Inspect selected research variant", variant)
  );
  append(section, selectedVariantCard);

  const overview = element("div", "panel-grid two");
  const sourceCard = card(`Research family · ${semanticFamilyLabel(family)}`);
  append(
    sourceCard,
    fieldGroup("Source family title — Slovenian", family.title_sl || family.title),
    fieldGroup("Source research purpose — Slovenian", family.purpose),
    fieldGroup("Family ID", familyId(family)),
    fieldGroup("Source hash", family.fixture?.source_hash),
    fieldGroup("Fixture SHA-256", family.fixture?.sha256),
    rawDetails("Inspect family metadata", {
      family_id: familyId(family),
      reviewer_status: family.reviewer_status,
      fixture: family.fixture,
      forbidden_shortcuts: family.forbidden_shortcuts,
    })
  );
  const scene = asObject(family.grounded_scene || family.scene);
  const sceneCard = card("Grounded source scene");
  append(
    sceneCard,
    fieldGroup(
      `Source scene input — ${semanticLanguageLabel(scene.language || "sl")}`,
      scene.raw_input || variant.input_text
    ),
    fieldGroup("Grounded evidence", asArray(scene.evidence).map((item) => item.evidence_id || item.source_ref || display(item)), { asChips: true }),
    fieldGroup(`Source unknowns — ${semanticLanguageLabel(scene.language || "sl")}`, scene.unknowns, { asChips: true }),
    fieldGroup("Allowed options", asArray(scene.options).map((item) => item.option_id || item), { asChips: true }),
    rawDetails("Inspect grounded SceneEvent", scene)
  );
  append(overview, sourceCard, sceneCard);
  append(section, overview);

  const sourceLocators = asArray(family.source_locators);
  const sourceSection = element("div", "subsection");
  append(sourceSection, subsectionTitle("Source traceability", `${sourceLocators.length} original-document locator${sourceLocators.length === 1 ? "" : "s"}`));
  const sourceGrid = element("div", "source-grid");
  sourceLocators.forEach((locator, index) => append(sourceGrid, sourceLocatorCard(locator, index)));
  if (!sourceLocators.length) append(sourceGrid, emptyNotice("No source locator", "This family cannot be treated as source-grounded."));
  append(sourceSection, sourceGrid);
  append(section, sourceSection);

  const bilingualSection = element("div", "subsection");
  append(bilingualSection, subsectionTitle("Slovenian / English source pair", "canonical source evidence beside its operational research gloss"));
  const bilingualGrid = element("div", "bilingual-grid");
  for (const [language, label] of [["sl", "Slovenian · canonical source evidence"], ["en", "English · operational research gloss"]]) {
    const item = bilingualText(family, variant, language);
    const languageCard = card(label, null, "language-card");
    append(
      languageCard,
      element("p", "language-copy", item.text || "No paired text is available."),
      fieldGroup("Variant", item.variant?.variant_id),
      rawDetails("Inspect language variant", item.variant || {})
    );
    append(bilingualGrid, languageCard);
  }
  append(bilingualSection, bilingualGrid);
  append(section, bilingualSection);

  const routeSection = element("div", "subsection");
  append(
    routeSection,
    subsectionTitle(
      "Expected route / actual evaluated route",
      semanticModeLabel(variant.mode || variant.language)
    )
  );
  const routeGrid = element("div", "route-grid");
  append(
    routeGrid,
    routeCard("Expected route", variant.expected_routes || variant.expected_route_ids, "Expected route unavailable"),
    routeCard("Actual evaluated route", variantActualRoutes(variant), "Not evaluated")
  );
  append(routeSection, routeGrid);
  const interpretationTruth = asArray(variant.expected_interpretation_truth);
  const truthCard = card("Expected interpretation truth");
  if (!interpretationTruth.length) {
    append(truthCard, emptyNotice("No interpretation truth", "This variant has no evaluator-side interpretation record."));
  } else {
    for (const truth of interpretationTruth) {
      const truthItem = element("div", "route-item");
      append(
        truthItem,
        choiceLine("Source mind", truth.source_mind),
        choiceLine("Interpretation", truth.interpretation_id),
        choiceLine("Native option", truth.native_option_id || truth.option_id),
        fieldGroup("Source native motive — original language", truth.native_motive_summary || truth.motive_summary),
        rawDetails("Inspect expected interpretation", truth)
      );
      append(truthCard, truthItem);
    }
  }
  append(routeSection, truthCard);
  const failures = variantFailureTags(variant, family);
  const resultPasses = asArray(evaluation.results).map((result) => result.passed);
  const evaluationPassed = resultPasses.length ? resultPasses.every(Boolean) : "not evaluated";
  const reviewCard = card("Review and failure status");
  append(
    reviewCard,
    keyValues([
      ["Variant reviewer status", variant.reviewer_status],
      ["Evaluation status", evaluation.status],
      ["Evaluation reason", evaluation.reason],
      ["Reviewer statuses", evaluation.reviewer_statuses],
      ["Actual labels", evaluation.actual_labels],
      ["Evaluation passed", evaluationPassed],
    ]),
    fieldGroup("Failure tags", failures, { asChips: true, emptyText: "No failure tags recorded" }),
    fieldGroup("Family failure tags", family.failure_tags, { asChips: true, emptyText: "No family-level failure tags recorded" }),
    rawDetails("Inspect variant and evaluation", { variant, evaluation })
  );
  append(routeSection, reviewCard);
  append(section, routeSection);
  return section;
}

function renderSemanticPanel({ focusControl = null } = {}) {
  const panel = els.panels.semantic;
  panel.replaceChildren();
  append(
    panel,
    panelHeading(
      "Semantic Lab · Research Corpus",
      "Read-only historical research families, test variants, reviewed routes, and benchmark evidence. Browsing this corpus never calls a model.",
      state.lab?.schema_version || "read-only"
    )
  );
  if (state.labError) {
    append(panel, emptyNotice("Semantic laboratory unavailable", state.labError));
    return;
  }
  if (!state.lab) {
    append(panel, emptyNotice("Loading semantic laboratory", "No cycle or model is started while this read-only evidence loads."));
    return;
  }

  append(panel, renderBenchmarkStatus(asObject(state.lab.benchmark_status || state.lab.benchmark)));
  const families = semanticFamilies();
  if (!state.selectedFamilyId || !families.some((item) => familyId(item) === state.selectedFamilyId)) {
    state.selectedFamilyId = familyId(families[0]);
  }
  const selected = families.find((item) => familyId(item) === state.selectedFamilyId);
  const picker = element("section", "subsection family-picker");
  append(picker, subsectionTitle("Research scenario family", `${families.length} source-grounded families`));
  const field = element("label", "field lab-field");
  append(field, element("span", "", "Scenario family"));
  const select = element("select", "lab-select");
  select.setAttribute("aria-label", "Semantic scenario family");
  for (const family of families) {
    const option = element("option", "", semanticFamilyLabel(family));
    option.value = familyId(family);
    option.selected = familyId(family) === state.selectedFamilyId;
    append(select, option);
  }
  select.addEventListener("change", () => {
    state.selectedFamilyId = select.value;
    state.selectedVariantId = null;
    renderSemanticPanel({ focusControl: "family" });
  });
  append(field, select);
  append(picker, field);
  append(panel, picker);
  if (selected) append(panel, renderSemanticFamily(selected));
  else append(panel, emptyNotice("No semantic families", "The endpoint returned no reviewable family records."));
  if (focusControl) {
    const label = focusControl === "family"
      ? "Semantic scenario family"
      : "Semantic variant";
    panel.querySelector(`[aria-label="${label}"]`)?.focus();
  }
}

function byMind(items, mind, index) {
  if (items && !Array.isArray(items) && typeof items === "object") {
    const named = items[mind === "E" ? "emocio" : "instinkt"];
    if (named) return named;
  }
  return asArray(items).find((item) => item?.source_mind === mind || item?.mind === mind) || asArray(items)[index] || {};
}

function shadowRegistryEntries() {
  const registry = asObject(state.shadowRegistry);
  const records = asArray(registry.evidence || registry.items);
  if (records.length) return records;
  const ids = asArray(
    registry.evidence_ids
      || state.bootstrap?.shadow_evidence_replay?.evidence_ids
  );
  return ids.map((evidenceId) => ({ evidence_id: evidenceId }));
}

function shadowEvidenceLabel(record) {
  const source = asObject(record);
  if (source.selector_label) return source.selector_label;
  if (source.label) return source.label;
  if (source.evidence_id === "en1-runtime") return "EN1 · English runtime shadow";
  if (source.evidence_id === "s1-partial") return "S1 · historical Slovene partial failure";
  if (source.evidence_id === "s1r-reconciled") return "S1R · historical Slovene reconciled success";
  return source.evidence_id || "Frozen shadow evidence";
}

function isCurrentEnglishShadowReplay(replay) {
  const source = asObject(replay);
  return source.kind === "current_runtime" && source.language === "en";
}

function redactShadowEvaluatorState() {
  const replay = asObject(state.shadowEvidence);
  const lanes = replay.lanes;
  if (!lanes) return;
  for (const lane of Array.isArray(lanes) ? lanes : Object.values(lanes)) {
    if (lane && typeof lane === "object") delete lane.debug_evaluator_ground_truth;
  }
}

function shadowDetailPath(evidenceId, debug = false) {
  const safeId = encodeURIComponent(evidenceId);
  return `/api/shadow-evidence/${safeId}?debug=${debug ? "true" : "false"}`;
}

async function loadShadowEvidence(
  evidenceId,
  { announce = true, render = true } = {}
) {
  if (!evidenceId) return;
  const requestGeneration = ++state.shadowRequestGeneration;
  const requestedDebug = els.debugToggle.checked;
  state.shadowAbortController?.abort();
  const abortController = new AbortController();
  state.shadowAbortController = abortController;
  state.shadowBusy = true;
  state.shadowEvidenceError = null;
  state.selectedShadowEvidenceId = evidenceId;
  if (announce) {
    setRuntime(
      "Reviewing frozen shadow evidence",
      "No model call will be made",
      "working"
    );
  }
  try {
    const evidence = await apiJson(
      shadowDetailPath(evidenceId, requestedDebug),
      { signal: abortController.signal }
    );
    if (
      requestGeneration !== state.shadowRequestGeneration
      || evidenceId !== state.selectedShadowEvidenceId
      || requestedDebug !== els.debugToggle.checked
    ) return;
    state.shadowEvidence = evidence;
    if (announce) {
      setRuntime(
        "Reviewing frozen shadow evidence",
        "No model call will be made",
        "ok"
      );
    }
  } catch (error) {
    if (
      requestGeneration !== state.shadowRequestGeneration
      || error?.name === "AbortError"
    ) return;
    state.shadowEvidence = null;
    state.shadowEvidenceError = error.message;
    if (announce) {
      setRuntime(
        "Frozen shadow evidence unavailable",
        "No model call was made",
        "error"
      );
    }
  } finally {
    if (requestGeneration === state.shadowRequestGeneration) {
      state.shadowBusy = false;
      state.shadowAbortController = null;
      if (render) renderRacioPanel(state.result?.panels?.racio);
    }
  }
}

function shadowEnumValue(label, value) {
  const line = element("div", "choice-line shadow-enum-line");
  append(line, element("span", "", label));
  const code = element("code", "shadow-enum", value === null || value === undefined || value === "" ? "not available" : value);
  append(line, code);
  return line;
}

function shadowCitations(label, values) {
  return fieldGroup(label, values, {
    asChips: true,
    emptyText: "No citations",
  });
}

function shadowObservationCard(observation, index, replay) {
  const source = asObject(observation);
  const text = asObject(source.text);
  const currentEnglish = isCurrentEnglishShadowReplay(replay);
  const canonicalSl = source.canonical_sl ?? text.canonical_sl;
  const operationalEn = source.operational_en ?? text.operational_en;
  const modelText = source.model_text ?? (currentEnglish ? source.text : canonicalSl);
  const item = element("article", "shadow-observation");
  item.dataset.observationId = source.observation_id || `observation-${index + 1}`;
  append(
    item,
    shadowEnumValue("Observation ID", source.observation_id),
    fieldGroup(
      currentEnglish
        ? "Current English model input"
        : "Historical exact model input — Slovenian",
      modelText || "The visible signal was degraded and contains no textual content."
    )
  );
  const metadata = [
    ["Channel", source.channel],
    ["Visibility", source.visibility ?? source.perception_status],
    ["Fidelity", source.fidelity],
    ["Provenance", source.provenance],
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");
  if (metadata.length) append(item, keyValues(metadata));
  if (operationalEn) {
    append(item, rawDetails("Historical operational English gloss — same evidence unit", operationalEn));
  }
  return item;
}

function shadowVisibleInputCard(visibleInput, sourceMind = null, replay = null) {
  const visible = asObject(visibleInput);
  const currentEnglish = isCurrentEnglishShadowReplay(replay);
  const observations = asArray(visible.observations || visible.visible_observations);
  const options = asArray(visible.public_options || visible.public_option_scope);
  const result = card(
    currentEnglish
      ? "1 · What Racio received"
      : "1 · Historical input received by Racio · Slovene model boundary",
    null,
    "shadow-visible-card"
  );
  result.dataset.shadowKind = "visible-input";
  append(
    result,
    keyValues([
      ["Source mind", visible.source_mind || sourceMind],
      ["Language", visible.language],
      ["Channel quality", visible.channel_quality],
      [currentEnglish ? "Presentation mode" : "Historical presentation mode", visible.presentation_mode],
    ]),
    fieldGroup("Degraded observations", visible.degraded_observation_ids, {
      asChips: true,
      emptyText: "None",
    }),
    fieldGroup("Omitted observations", visible.omitted_observation_ids, {
      asChips: true,
      emptyText: "None",
    })
  );
  if (currentEnglish) {
    append(result, fieldGroup("Model-facing uncertainty", visible.uncertainty));
  }
  const observationList = element("div", "shadow-observation-list");
  observations.forEach((observation, index) => append(
    observationList,
    shadowObservationCard(observation, index, replay)
  ));
  append(
    result,
    fieldGroup("Visible observation units", observations.length ? `${observations.length}` : "No visible observations"),
    observationList
  );
  const optionList = element("div", "shadow-option-scope");
  for (const option of options) {
    const record = asObject(option);
    const text = asObject(record.text);
    const optionItem = element("div", "shadow-option-item");
    append(
      optionItem,
      shadowEnumValue("Option ID", record.option_id),
      fieldGroup(
        currentEnglish
          ? "Current English public option"
          : "Historical public option text — Slovenian exact model input",
        currentEnglish
          ? record.model_text
          : record.canonical_sl ?? text.canonical_sl
      )
    );
    const english = record.operational_en ?? text.operational_en;
    if (english) append(optionItem, rawDetails("Historical operational English gloss", english));
    append(optionList, optionItem);
  }
  append(
    result,
    fieldGroup("Public option scope", options.length ? `${options.length} options` : "Empty public scope"),
    optionList,
    rawDetails("Inspect the stored packet artifact", visible.raw_details || visible)
  );
  return result;
}

function shadowExactModelInputCard(exactInput) {
  const exact = asObject(exactInput);
  const complete = exact.availability === "complete";
  const result = card("Exact input sent to Gemma", null, "shadow-exact-input-card");
  result.dataset.shadowKind = "exact-model-input";
  append(
    result,
    statusPill("exact request", complete ? "available" : "not preserved"),
    element(
      "p",
      "shadow-source-note",
      complete
        ? "This is the exact system instruction, user packet, output schema, and call configuration used for this result."
        : "This historical evidence preserved the packet but not a complete replayable provider request."
    )
  );
  if (complete) {
    append(
      result,
      keyValues([
        ["Model", exact.model],
        ["Streaming", exact.stream],
        ["Separate private thinking requested", exact.think],
      ]),
      rawDetails("Exact system instruction", exact.system_instruction),
      rawDetails("Exact user packet JSON", exact.user_packet_json),
      rawDetails("Exact output schema", exact.output_schema),
      rawDetails("Exact generation settings", exact.options),
      rawDetails("Exact ProviderCallSpec", exact.call_spec),
      rawDetails("Complete sanitized request payload", exact.exact_request)
    );
  } else {
    append(
      result,
      rawDetails("Stored packet artifact", exact.packet_artifact),
      rawDetails("Stored ProviderCallSpec", exact.call_spec)
    );
  }
  return result;
}

function uncertaintyPlainText(value) {
  if (value === "not_reported") return "Gemma did not say whether Racio was uncertain.";
  if (value === "uncertain") return "Gemma reported that Racio was uncertain.";
  if (value === "not_uncertain") return "Gemma reported that Racio was not uncertain.";
  return value || "Not available";
}

function shadowExplanationBlock(label, explanation) {
  const source = asObject(explanation);
  const block = element("div", "shadow-explanation-block");
  append(
    block,
    element("h4", "", label),
    fieldGroup(
      "Gemma's explanation",
      source.explanation || "Gemma did not provide an explanation."
    )
  );
  if (source.explanation) {
    append(
      block,
      shadowCitations(
        "Observations cited by Gemma",
        source.cited_observation_ids
      )
    );
  }
  return block;
}

function shadowPlainSummaryCard(lane) {
  const source = asObject(lane);
  const shadow = asObject(source.shadow);
  const explanations = asObject(shadow.model_authored_abstention_explanations);
  const shape = source.presentation_shape;
  const result = card("Result in plain language", null, "shadow-plain-summary-card");
  result.dataset.shadowKind = "plain-summary";
  if (shape === "full_abstention") {
    append(
      result,
      element("strong", "", "Gemma made no action, option, or motive claim."),
      element(
        "p",
        "",
        shadow.model_explanation_status === "provided"
          ? "Gemma supplied the cited explanations shown below."
          : "Gemma did not explain why. Any standard unknown text shown elsewhere was added by deterministic code."
      )
    );
  } else if (shape === "action_only") {
    append(
      result,
      element("strong", "", "Gemma made an action claim only."),
      element("p", "", "Gemma did not select an option or claim a motive.")
    );
  } else if (shape === "failed") {
    append(
      result,
      element("strong", "", "The Gemma comparison failed; REI still completed normally."),
      element("p", "", "No accepted Gemma interpretation was published.")
    );
  } else {
    append(result, element("strong", "", "Gemma returned bounded review-only claims."));
  }
  if (shadow.status === "succeeded") {
    const actionClaims = asArray(shadow.action_hypotheses);
    const optionClaim = asObject(shadow.option_inference);
    const motiveClaims = asArray(shadow.motive_hypotheses);
    const absenceExplanations = [];
    if (actionClaims.length === 0) {
      absenceExplanations.push(
        shadowExplanationBlock("Why no action claim?", explanations.action)
      );
    }
    if (Object.keys(optionClaim).length === 0) {
      absenceExplanations.push(
        shadowExplanationBlock("Why no option claim?", explanations.option)
      );
    }
    if (motiveClaims.length === 0) {
      absenceExplanations.push(
        shadowExplanationBlock("Why no motive claim?", explanations.motive)
      );
    }
    append(
      result,
      ...absenceExplanations,
      keyValues([
        ["Option uncertainty", uncertaintyPlainText(asObject(shadow.uncertainty).option_mapping)],
        ["Motive uncertainty", uncertaintyPlainText(asObject(shadow.uncertainty).motive_interpretation)],
      ])
    );
  }
  return result;
}

function shadowCanonicalizerCard(shadow) {
  const source = asObject(shadow);
  const additions = asArray(source.canonicalizer_additions);
  const result = card(
    "4 · System-added text — not written by Gemma",
    null,
    "shadow-canonicalizer-card"
  );
  result.dataset.shadowKind = "canonicalizer-additions";
  append(
    result,
    element(
      "p",
      "shadow-source-note",
      "The deterministic canonicalizer added these standard placeholders so the stored result satisfies the frozen V3 structure. They are not Gemma explanations."
    )
  );
  if (!additions.length) {
    append(result, fieldGroup("Added fields", "None"));
    return result;
  }
  const list = element("div", "shadow-canonicalizer-list");
  additions.forEach((addition) => {
    const item = asObject(addition);
    append(
      list,
      fieldGroup(`${item.claim_kind || "Claim"} placeholder`, item.value),
      shadowEnumValue("Stored field", item.field)
    );
  });
  append(result, list);
  return result;
}

function shadowAuthoritativeCard(authoritative) {
  const source = asObject(authoritative);
  const result = card(
    "2 · Authoritative Racio — used by REI",
    null,
    "shadow-authoritative-card"
  );
  result.dataset.shadowKind = "authoritative";
  append(
    result,
    statusPill("authoritative cycle", source.status || "succeeded"),
    keyValues([
      ["Action tendency", source.action_tendency ?? source.inferred_action_tendency],
      ["Inferred option", source.option_id ?? source.inferred_option_id],
      ["Confidence", source.confidence],
      ["Interpretation ID", source.interpretation_id],
    ]),
    fieldGroup("Motive summary", source.motive_summary ?? source.inferred_motive),
    rawDetails("Inspect authoritative interpretation", source.raw_details || source)
  );
  return result;
}

function shadowActionClaim(claim, index) {
  const source = asObject(claim);
  const item = element("div", "shadow-claim shadow-action-claim");
  append(
    item,
    element("h4", "", `Action claim ${index + 1}`),
    shadowEnumValue("Family", source.family),
    shadowEnumValue("Subtype", source.subtype ?? source.family_fallback),
    shadowEnumValue("Support mode", source.support_mode),
    choiceLine("Confidence", source.confidence),
    shadowCitations("Action citations", source.citations || source.cited_observation_ids)
  );
  return item;
}

function shadowMotiveClaim(claim, index) {
  const source = asObject(claim);
  const item = element("div", "shadow-claim shadow-motive-claim");
  append(
    item,
    element("h4", "", `Motive hypothesis ${index + 1}`),
    shadowEnumValue("Family", source.family),
    shadowEnumValue("Subtype", source.subtype),
    shadowEnumValue("Support mode", source.support_mode),
    choiceLine("Confidence", source.confidence),
    shadowCitations("Motive citations", source.citations || source.cited_observation_ids)
  );
  return item;
}

function inferredShadowShape(shadow, preferredShape = null) {
  if (preferredShape) return preferredShape;
  const source = asObject(shadow);
  if (source.status === "failed") return "failed";
  const output = asObject(source.structured_output || source.interpretation);
  const actions = asArray(source.action_hypotheses || output.action_hypotheses);
  const option = source.option_inference ?? output.option_inference;
  const motives = asArray(source.motive_hypotheses || output.motive_hypotheses);
  if (!actions.length && !option && !motives.length) return "full_abstention";
  if (actions.length && !option && !motives.length) return "action_only";
  return "bounded_claims";
}

function shadowStatusNotice(shadow, presentationShape) {
  const source = asObject(shadow);
  const shape = inferredShadowShape(source, presentationShape);
  const notice = element("div", `shadow-status-notice ${shape}`);
  notice.dataset.shadowStatus = shape;
  if (shape === "full_abstention") {
    append(
      notice,
      element("strong", "", "Gemma made no claim"),
      element("p", "", "No action, option, or motive claim was returned.")
    );
  } else if (shape === "action_only") {
    append(
      notice,
      element("strong", "", "Gemma made an action claim only"),
      element("p", "", "The option and motive remained unresolved.")
    );
  } else if (shape === "failed") {
    append(
      notice,
      element("strong", "", "Gemma shadow branch failed"),
      element("p", "", "The authoritative deterministic cycle still succeeded; no accepted shadow interpretation was published.")
    );
  } else {
    append(
      notice,
      element("strong", "", "Gemma returned review-only claims"),
      element("p", "", "The displayed claims did not affect REI.")
    );
  }
  return notice;
}

function shadowInterpretationCard(shadow, presentationShape, replay = null) {
  const source = asObject(shadow);
  const currentEnglish = isCurrentEnglishShadowReplay(replay);
  const output = asObject(source.structured_output || source.interpretation);
  const actions = asArray(source.action_hypotheses || output.action_hypotheses);
  const option = asObject(source.option_inference || output.option_inference);
  const motives = asArray(source.motive_hypotheses || output.motive_hypotheses);
  const uncertainty = asObject(
    source.uncertainty
      || source.racio_reported_uncertainty
      || output.racio_reported_uncertainty
  );
  const failure = asObject(source.failure);
  const result = card(
    currentEnglish
      ? "3 · Exact Gemma result — for review only"
      : "3 · Historical Gemma result — for review only",
    null,
    "shadow-model-card"
  );
  result.dataset.shadowKind = "shadow";
  append(
    result,
    shadowStatusNotice(source, presentationShape),
    statusPill("shadow status", source.status),
    statusPill("no_authority", source.no_authority),
    shadowEnumValue("Semantic shape", inferredShadowShape(source, presentationShape)),
    choiceLine(
      "Accepted shadow interpretation published",
      source.accepted_interpretation_published
    )
  );
  if (source.status === "failed") {
    append(
      result,
      keyValues([
        ["Failure stage", failure.stage ?? source.failure_stage],
        ["Failure code", failure.code ?? source.failure_code],
      ]),
      fieldGroup("Bounded failure summary", failure.summary ?? source.failure_summary)
    );
  } else {
    const actionClaims = element("div", "shadow-claim-list");
    actions.forEach((claim, index) => append(actionClaims, shadowActionClaim(claim, index)));
    append(
      result,
      fieldGroup("Action hypotheses", actions.length ? `${actions.length}` : "No action claim"),
      actionClaims
    );

    const optionSection = element("div", "shadow-claim shadow-option-claim");
    append(optionSection, element("h4", "", "Option inference"));
    if (Object.keys(option).length) {
      append(
        optionSection,
        shadowEnumValue("Option ID", option.option_id),
        choiceLine("Confidence", option.confidence),
        shadowCitations("Option-specific citations", option.citations || option.cited_observation_ids)
      );
    } else {
      append(
        optionSection,
        fieldGroup("Status", "No option claim")
      );
    }
    append(result, optionSection);

    const motiveClaims = element("div", "shadow-claim-list");
    motives.forEach((claim, index) => append(motiveClaims, shadowMotiveClaim(claim, index)));
    append(
      result,
      fieldGroup("Motive hypotheses", motives.length ? `${motives.length}` : "No motive claim"),
      motiveClaims,
      keyValues([
        ["Option uncertainty", uncertaintyPlainText(uncertainty.option_mapping)],
        ["Motive uncertainty", uncertaintyPlainText(uncertainty.motive_interpretation)],
      ])
    );
  }
  append(
    result,
    rawDetails("Exact JSON returned by Gemma", source.model_draft),
    rawDetails("Canonical accepted interpretation", asObject(source.raw_details).interpretation),
    rawDetails("Inspect complete safe shadow artifact", source.raw_details || source)
  );
  return result;
}

function comparisonValue(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    if (value.comparable === false) {
      return value.reason ? `not available · ${value.reason}` : "not available";
    }
    if (value.comparable === true) return comparisonValue(value.value);
  }
  return value === null || value === undefined || value === ""
    ? "not available"
    : value;
}

function shadowComparisonCard(comparison) {
  const source = asObject(comparison);
  const citationDifferences = asObject(source.citation_differences);
  const uncertaintyDifferences = asObject(source.uncertainty_differences);
  const result = card("Diagnostic comparison · no aggregate score", null, "shadow-comparison-card");
  result.dataset.shadowKind = "comparison";
  append(
    result,
    keyValues([
      ["Option agreement", comparisonValue(source.option_agreement ?? source.option_mapping_matches)],
      ["Action-family agreement", comparisonValue(source.action_family_agreement ?? source.action_family_matches)],
      ["Action-subtype agreement", comparisonValue(source.action_subtype_agreement ?? source.action_subtype_matches)],
      ["Motive-family overlap", comparisonValue(source.motive_family_overlap)],
      ["Motive-subtype overlap", comparisonValue(source.motive_subtype_overlap)],
      ["Citation comparison", comparisonValue(citationDifferences)],
      ["Uncertainty comparison", comparisonValue(uncertaintyDifferences)],
    ]),
    shadowCitations(
      "Authoritative supporting observation IDs",
      citationDifferences.authoritative_supporting_observation_ids
    ),
    shadowCitations("Shadow action citations", citationDifferences.shadow_action_citations),
    shadowCitations("Shadow option citations", citationDifferences.shadow_option_citations),
    shadowCitations("Shadow motive citations", citationDifferences.shadow_motive_citations),
    keyValues([
      ["Authoritative uncertainty", comparisonValue(uncertaintyDifferences.authoritative)],
      ["Shadow option uncertainty", comparisonValue(asObject(uncertaintyDifferences.shadow).option_mapping)],
      ["Shadow motive uncertainty", comparisonValue(asObject(uncertaintyDifferences.shadow).motive_interpretation)],
    ]),
    rawDetails("Inspect safe diagnostic comparison", source.raw_details || source)
  );
  return result;
}

function shadowDebugCard(debugTruth) {
  const source = asObject(debugTruth);
  if (!Object.keys(source).length) return null;
  const result = card("DEBUG / EVALUATOR GROUND TRUTH", null, "debug-card shadow-debug-card");
  result.dataset.shadowKind = "debug-ground-truth";
  append(
    result,
    element("strong", "debug-boundary-copy", RACIO_GROUND_TRUTH_WARNING),
    element(
      "p",
      "debug-boundary-copy",
      "Neither the Gemma shadow nor authoritative Racio received these values; they are visible only through the local evaluator-debug boundary."
    ),
    keyValues([
      ["Native option", source.native_option_id],
      ["Native action tendency", source.native_action_tendency],
      ["Gap status", source.gap_status],
      ["Distortion", source.distortion_type],
      ["Option match", source.option_match],
      ["Motive fidelity", source.motive_fidelity],
    ]),
    fieldGroup("Native motive", source.native_motive_summary),
    rawDetails("Inspect evaluator-only ground truth", source.raw_details || source)
  );
  return result;
}

function shadowAdvancedDetails(title, child) {
  const details = element("details", "shadow-advanced-details");
  append(details, element("summary", "", title), child);
  return details;
}

function shadowLaneSection(lane, mind, index, replay = null) {
  const source = asObject(lane);
  const label = source.mind_label || (mind === "E" ? "Emocio" : "Instinkt");
  const section = element("section", `shadow-lane ${mind === "E" ? "emocio" : "instinkt"}`);
  section.dataset.shadowMind = mind;
  append(
    section,
    subsectionTitle(`${label} → Racio`, `source mind ${source.source_mind || mind}`),
    shadowPlainSummaryCard(source),
    shadowVisibleInputCard(source.visible_input, source.source_mind || mind, replay),
    shadowExactModelInputCard(source.exact_model_input)
  );
  const pair = element("div", "shadow-interpretation-grid");
  append(
    pair,
    shadowAuthoritativeCard(source.authoritative),
    shadowInterpretationCard(source.shadow, source.presentation_shape, replay)
  );
  append(
    section,
    pair,
    shadowCanonicalizerCard(source.shadow),
    shadowAdvancedDetails(
      "Advanced diagnostic comparison",
      shadowComparisonCard(source.diagnostic_comparison)
    ),
    shadowDebugCard(source.debug_evaluator_ground_truth),
    rawDetails(`Inspect complete safe ${label} replay lane`, source.raw_details || source)
  );
  return section;
}

function renderShadowReplaySection() {
  const section = element("section", "subsection shadow-replay-section");
  section.dataset.shadowSection = "gemma-text-shadow";
  append(
    section,
    subsectionTitle(
      "Gemma Text Shadow",
      "frozen read-only evidence · no authority"
    )
  );
  const entries = shadowRegistryEntries();
  if (state.shadowRegistryError) {
    append(section, emptyNotice("Shadow evidence registry unavailable", state.shadowRegistryError));
    return section;
  }
  const controls = element("div", "shadow-replay-controls");
  const field = element("label", "field shadow-evidence-field");
  append(field, element("span", "", "Frozen evidence replay"));
  const select = element("select", "shadow-evidence-select");
  select.id = "shadowEvidenceSelect";
  select.setAttribute("aria-label", "Frozen Gemma shadow evidence");
  select.disabled = state.shadowBusy || !entries.length;
  const evidenceGroups = [
    ["CURRENT RUNTIME EVIDENCE", entries.filter((record) => asObject(record).kind === "current_runtime")],
    ["HISTORICAL EVIDENCE", entries.filter((record) => asObject(record).kind !== "current_runtime")],
  ];
  for (const [groupLabel, records] of evidenceGroups) {
    if (!records.length) continue;
    const group = element("optgroup");
    group.label = groupLabel;
    for (const record of records) {
      const source = asObject(record);
      const option = element("option", "", shadowEvidenceLabel(source));
      option.value = source.evidence_id;
      option.selected = source.evidence_id === state.selectedShadowEvidenceId;
      append(group, option);
    }
    append(select, group);
  }
  select.addEventListener("change", () => loadShadowEvidence(select.value));
  append(field, select);
  const boundary = element("div", "shadow-boundary-copy");
  const selectedRecord = asObject(
    entries.find((record) => asObject(record).evidence_id === state.selectedShadowEvidenceId)
  );
  const currentEnglishSelection = isCurrentEnglishShadowReplay(selectedRecord);
  append(
    boundary,
    element("strong", "", "Reviewing frozen shadow evidence"),
    element(
      "span",
      "",
      currentEnglishSelection
        ? "Current English runtime replay. No model call will be made."
        : "Historical · Slovene model boundary · retained for provenance · not the active runtime language contract."
    )
  );
  append(controls, field, boundary);
  append(section, controls);
  if (state.shadowEvidenceError) {
    append(section, emptyNotice("Evidence could not be displayed", state.shadowEvidenceError));
    return section;
  }
  const replay = asObject(state.shadowEvidence);
  if (!Object.keys(replay).length) {
    append(section, emptyNotice("Evidence is loading", "Select registered current or historical evidence."));
    return section;
  }
  if (replay.historical) {
    append(
      section,
      element(
        "div",
        "shadow-history-banner",
        "HISTORICAL · SLOVENE MODEL BOUNDARY · RETAINED FOR PROVENANCE · NOT THE ACTIVE RUNTIME LANGUAGE CONTRACT"
      )
    );
  }
  append(
    section,
    element("div", "shadow-no-authority-banner", "GEMMA TEXT SHADOW · NO AUTHORITY"),
    statusPill("no_authority", replay.no_authority),
    keyValues([
      ["Evidence", replay.label],
      ["Evidence ID", replay.evidence_id],
      ["Phase", replay.phase],
      ["Evidence kind", replay.kind],
      ["Model boundary language", replay.language],
      ["Authority", replay.authority],
      ["Live model execution", replay.live_model_execution],
      ["Cold verification", asObject(replay.integrity).status || asObject(replay.integrity).cold_verified],
    ]),
    fieldGroup("Frozen evidence summary", replay.summary)
  );
  const lanes = replay.lanes;
  const laneTabs = element("div", "shadow-mind-tabs");
  laneTabs.setAttribute("role", "tablist");
  laneTabs.setAttribute("aria-label", "Racio shadow source mind");
  for (const [mind, label] of [["E", "Emocio"], ["I", "Instinkt"]]) {
    const button = element("button", "shadow-mind-tab", label);
    button.type = "button";
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(state.selectedShadowMind === mind));
    button.dataset.shadowMind = mind;
    button.addEventListener("click", () => {
      state.selectedShadowMind = mind;
      renderRacioPanel(state.result?.panels?.racio);
    });
    append(laneTabs, button);
  }
  const laneStack = element("div", "shadow-lane-stack");
  const selectedMind = state.selectedShadowMind === "I" ? "I" : "E";
  const selectedIndex = selectedMind === "E" ? 0 : 1;
  append(
    laneStack,
    shadowLaneSection(
      byMind(lanes, selectedMind, selectedIndex),
      selectedMind,
      selectedIndex,
      replay
    )
  );
  append(
    section,
    laneTabs,
    laneStack,
    rawDetails("Inspect complete safe frozen replay", replay.raw_details || replay)
  );
  return section;
}

function renderRacioPanel(payload) {
  const panel = els.panels.racio;
  panel.replaceChildren();
  if (!payload) {
    append(panel, panelHeading("Racio Interpretation", "Run an explicit deterministic cycle to inspect Racio's visible inputs."));
    append(panel, emptyNotice("No cycle yet", "Bootstrap never starts a cycle automatically."));
    append(panel, renderShadowReplaySection());
    return;
  }
  const racio = asObject(payload);
  const debugTruthRecord = els.debugToggle.checked
    ? asObject(racio.evaluator_ground_truth)
    : {};
  const debugTruth = Object.keys(debugTruthRecord).length ? debugTruthRecord : null;
  append(
    panel,
    panelHeading(
      "Racio Interpretation",
      "Observable input and fallible interpretation are kept separate from evaluator-only native truth.",
      debugTruth ? "local debug visible" : "runtime view"
    )
  );
  const boundary = element("div", "warning-banner epistemic-warning");
  const warningDetail = String(racio.warning || "").replace(RACIO_GROUND_TRUTH_WARNING, "").trim();
  append(boundary, element("strong", "", RACIO_GROUND_TRUTH_WARNING), document.createTextNode(warningDetail ? ` ${warningDetail}` : ""));
  append(panel, boundary);

  const conclusion = card("Racio native conclusion");
  append(
    conclusion,
    choiceLine("Native option", racio.native_conclusion?.option_id),
    fieldGroup("Facts used", racio.native_conclusion?.facts_used, { asChips: true }),
    fieldGroup("Unknowns", racio.native_conclusion?.unknowns, { asChips: true }),
    fieldGroup("Causal sequence", racio.native_conclusion?.causal_sequence, { asChips: true }),
    rawDetails("Inspect Racio conclusion", racio.native_conclusion)
  );
  append(panel, conclusion);

  const comparison = element("div", "racio-comparison-stack");
  for (const [mind, index, label] of [["E", 0, "Emocio"], ["I", 1, "Instinkt"]]) {
    const visible = byMind(racio.visible_inputs, mind, index);
    const manifestation = byMind(racio.manifestations, mind, index);
    const interpretation = byMind(racio.interpretations, mind, index);
    const gap = byMind(racio.translation_gaps, mind, index);
    const truth = debugTruth ? byMind(debugTruth, mind, index) : null;
    const visibleObservations = asArray(visible.observable_views).flatMap((view) => asArray(view.observations));
    const row = element("section", `racio-case ${mind === "E" ? "emocio" : "instinkt"}`);
    append(row, subsectionTitle(`${label} → Racio`, truth ? "evaluator comparison enabled" : "ground truth withheld"));
    const grid = element("div", `racio-grid ${truth ? "debug" : ""}`.trim());
    const seen = card("What Racio actually saw", null, "racio-visible-card");
    append(
      seen,
      keyValues([
        ["Source mind", visible.source_mind],
        ["Relation direction", visible.relation_direction],
        ["Acceptance state", visible.acceptance_state_id],
      ]),
      fieldGroup("Visible observations", visibleObservations.map((observation) => observation.content || `${observation.signal_name}=${observation.canonical_json_value}`), { asChips: true }),
      fieldGroup("Allowed options", visible.allowed_option_ids, { asChips: true }),
      fieldGroup("Manifestation", Object.entries(manifestation).filter(([key, value]) => typeof value !== "object" && !key.includes("hash")).slice(0, 8).map(([key, value]) => `${humanize(key)}: ${display(value)}`), { asChips: true }),
      rawDetails("Exact conscious-access input", visible),
      rawDetails("Exact manifestation", manifestation)
    );
    const interpreted = card("Racio translation", null, "racio-interpretation-card");
    append(
      interpreted,
      keyValues([
        ["Inferred option", interpretation.inferred_option_id],
        ["Inferred tendency", interpretation.inferred_action_tendency],
        ["Confidence", interpretation.confidence],
        ["Status", interpretation.status || interpretation.interpretation_status],
      ]),
      fieldGroup("Inferred motive", interpretation.inferred_motive || interpretation.inferred_motive_class),
      fieldGroup("Alternative hypotheses", interpretation.alternative_hypotheses, { asChips: true }),
      rawDetails("Exact interpretation", interpretation)
    );
    append(grid, seen, interpreted);
    if (truth) {
      const evaluator = card("Debug · evaluator only", null, "debug-card");
      append(
        evaluator,
        element("strong", "debug-boundary-copy", RACIO_GROUND_TRUTH_WARNING),
        choiceLine("Evaluator label", byMind(racio.evaluator_labels, mind, index) || racio.evaluator_labels?.[mind === "E" ? "emocio" : "instinkt"]),
        choiceLine("Native option", truth.native_option_id),
        fieldGroup("Native motive", truth.native_motive_summary),
        keyValues([
          ["Gap status", gap.gap_status],
          ["Distortion", gap.distortion_type],
          ["Option match", gap.option_match],
          ["Motive fidelity", gap.motive_fidelity],
        ]),
        rawDetails("Evaluator ground truth", truth),
        rawDetails("TranslationGap", gap)
      );
      append(grid, evaluator);
    }
    append(row, grid);
    append(comparison, row);
  }
  append(
    panel,
    comparison,
    rawDetails("Inspect complete safe Racio panel", racio),
    renderShadowReplaySection()
  );
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
    append(placeholder, element("strong", "", "No rendered image artifact"), element("span", "", "The structured scene remains authoritative; no pixels are invented."));
    append(well, placeholder);
  }
  const body = element("div", "scene-body");
  append(
    body,
    element("h4", "", humanize(scene.scene_kind || slot.scene_kind || "visual scene")),
    element("p", "", asArray(scene.composition).join(" · ") || compactId(slot.scene_id)),
    statusPill("image", slot.status || "not rendered")
  );
  if (scene.option_id || slot.option_id) append(body, choiceLine("Option", scene.option_id || slot.option_id));
  if (valuation) {
    append(
      body,
      fieldGroup("Structured valuation", asArray(valuation.dimensions).map((dimension) => `${humanize(dimension.name)} ${display(dimension.score)}`), { asChips: true }),
      rawDetails("Inspect structured valuation", valuation)
    );
  }
  if (slot.artifact?.generated_only_elements?.length) {
    append(body, fieldGroup("Renderer-added · ungrounded", slot.artifact.generated_only_elements, { asChips: true }));
  }
  append(wrapper, well, body);
  return wrapper;
}

function renderEmocioPanel(payload) {
  const panel = els.panels.emocio;
  panel.replaceChildren();
  if (!payload) {
    append(panel, panelHeading("Emocio", "Run an explicit deterministic cycle to inspect structured and visual cognition."));
    append(panel, emptyNotice("No cycle yet", "No renderer or encoder is contacted during bootstrap."));
    return;
  }
  const emocio = asObject(payload);
  const visualStatus = asObject(emocio.visual_status);
  append(
    panel,
    panelHeading(
      "Emocio",
      "Scene construction, image lineage, embeddings, and structured versus visual valuation remain separate.",
      visualStatus.effective_mode || visualStatus.requested_mode || "structured"
    )
  );
  const statusStrip = element("div", "status-strip");
  append(
    statusStrip,
    statusPill("requested mode", visualStatus.requested_mode),
    statusPill("effective mode", visualStatus.effective_mode),
    statusPill("embeddings", visualStatus.embedding_status),
    statusPill("similarity", visualStatus.similarity_status)
  );
  append(panel, statusStrip);
  if (visualStatus.renderer_warning || visualStatus.visual_warning) {
    const warning = element("div", "warning-banner");
    append(warning, element("strong", "", "Visual runtime status"), document.createTextNode(` ${visualStatus.renderer_warning || visualStatus.visual_warning}`));
    append(panel, warning);
  }

  const conclusionGrid = element("div", "panel-grid two");
  const structured = card("Structured valuation and conclusion");
  append(
    structured,
    choiceLine("Structured option", emocio.structured_conclusion?.option_id),
    fieldGroup("Desired transformation", emocio.structured_conclusion?.desired_transformation),
    fieldGroup("Valuation dimensions", emocio.structured_conclusion?.valuation_dimensions, { asChips: true }),
    rawDetails("Inspect structured conclusion", emocio.structured_conclusion),
    rawDetails("Inspect structured valuations", emocio.structured_valuations)
  );
  const effective = card("Effective native conclusion");
  append(
    effective,
    choiceLine("Native option", emocio.native_option_id),
    choiceLine("Conclusion source", emocio.cognition_trace?.conclusion_source),
    fieldGroup("Action tendency", emocio.conclusion?.action_tendency),
    fieldGroup("Uncertainty", emocio.conclusion?.uncertainty),
    rawDetails("Inspect cognition trace", emocio.cognition_trace),
    rawDetails("Inspect native conclusion", emocio.conclusion)
  );
  append(conclusionGrid, structured, effective);
  append(panel, conclusionGrid);

  const scenes = element("section", "subsection");
  const slots = asArray(emocio.image_slots);
  append(scenes, subsectionTitle("Current / desired / broken / option rollouts", `${slots.length} scene slots`));
  const valuationsByScene = new Map(asArray(emocio.structured_valuations).map((item) => [item.rollout_scene_id, item]));
  const sceneGrid = element("div", "scene-grid");
  for (const slot of slots) append(sceneGrid, renderSceneSlot(slot, valuationsByScene.get(slot.scene_id)));
  if (!slots.length) {
    for (const scene of asArray(emocio.scene_specs)) {
      append(sceneGrid, renderSceneSlot({ scene, scene_id: scene.scene_id, scene_kind: scene.scene_kind, option_id: scene.option_id, status: "not_rendered" }));
    }
  }
  append(scenes, sceneGrid, rawDetails("Inspect exact scene specs", emocio.scene_specs));
  append(panel, scenes);

  const visualSection = element("section", "subsection");
  append(visualSection, subsectionTitle("Embeddings and similarity", visualStatus.similarity_status || "not executed"));
  const observations = asArray(emocio.visual_observations);
  const observationGrid = element("div", "panel-grid two");
  for (const observation of observations) {
    const observationCard = card(`${humanize(observation.role)} embedding`);
    append(
      observationCard,
      keyValues([
        ["Observation", observation.observation_id],
        ["Scene", observation.scene_spec_id],
        ["Encoding", observation.encoding_id],
        ["Dimensions", observation.embedding?.dimensions],
        ["Vector hash", observation.embedding?.vector_hash],
        ["Internal only", observation.internal_only],
        ["External evidence claim", observation.external_evidence_claim],
      ]),
      fieldGroup("Ungrounded imagined elements", observation.imagined?.ungrounded_elements, { asChips: true }),
      rawDetails("Inspect embedding lineage", observation)
    );
    append(observationGrid, observationCard);
  }
  if (!observations.length) append(observationGrid, emptyNotice("Embeddings not executed in this cycle", "Structured scenes remain available without simulated similarity values."));
  append(visualSection, observationGrid);

  const valuation = asObject(emocio.visual_valuation);
  if (Object.keys(valuation).length) {
    const valuationCard = card("Visual valuation");
    append(
      valuationCard,
      keyValues([
        ["Current ↔ desired similarity", valuation.current_desired_similarity],
        ["Leading option", valuation.leading_option_id],
        ["Tied options", valuation.tied_option_ids],
        ["Mean uncertainty", valuation.mean_uncertainty],
        ["Integration disposition", valuation.integration_disposition],
      ]),
      fieldGroup("Option scores", asArray(valuation.option_scores).map((score) => `${score.option_id}: ${display(score.fused_score ?? score.score)}`), { asChips: true }),
      rawDetails("Inspect visual comparisons and scores", valuation)
    );
    append(visualSection, valuationCard);
  } else {
    append(
      visualSection,
      emptyNotice(
        "Visual valuation not executed in this cycle",
        "The structured valuation remains separate and no visual score is simulated."
      )
    );
  }
  append(panel, visualSection);

  const ungrounded = asArray(emocio.renderer_added_ungrounded_elements);
  const provenanceSection = element("section", "subsection");
  append(provenanceSection, subsectionTitle("Renderer-added elements", "always ungrounded internal artifacts"));
  if (!ungrounded.length) {
    append(provenanceSection, emptyNotice("No renderer-added elements", "No generated image was admitted in this cycle."));
  } else {
    for (const record of ungrounded) {
      const recordCard = card(compactId(record.image_id));
      append(recordCard, choiceLine("Scene", record.source_spec_id), fieldGroup("Ungrounded elements", record.elements, { asChips: true }), rawDetails("Inspect provenance", record));
      append(provenanceSection, recordCard);
    }
  }
  append(provenanceSection, rawDetails("Inspect generated image metadata", emocio.generated_images));
  append(panel, provenanceSection, rawDetails("Inspect complete Emocio panel", emocio));
}

function bodyBars(bodyState) {
  const bars = element("div", "body-bars");
  for (const dimension of BODY_DIMENSIONS) {
    const raw = Number(bodyState?.[dimension]);
    const value = Number.isFinite(raw) ? Math.max(0, Math.min(1, raw)) : 0;
    const row = element("div", "body-bar");
    const track = element("span", "bar-track");
    const fill = element("span", "bar-fill");
    fill.style.width = `${value * 100}%`;
    append(track, fill);
    append(row, element("span", "", humanize(dimension)), track, element("output", "", display(Number.isFinite(raw) ? raw : null)));
    append(bars, row);
  }
  return bars;
}

function renderRollout(rollout, decisiveRolloutId = null) {
  const wrapper = element("details", "card body-trajectory");
  wrapper.open = rollout.rollout_id === decisiveRolloutId;
  append(
    wrapper,
    element("summary", "", `${rollout.option_id || "option"} · loss ${display(rollout.predicted_loss)} · recovery ${display(rollout.recoverability)}`),
    keyValues([
      ["Alarm", rollout.dominant_alarm],
      ["Boundary", rollout.boundary_outcome],
      ["Trust", rollout.trust_outcome],
      ["Attachment", rollout.attachment_outcome],
      ["Escape", rollout.escape_outcome],
    ]),
    fieldGroup("Association matches", rollout.association_match_ids, { asChips: true })
  );
  asArray(rollout.trajectory).forEach((bodyState, index) => {
    const step = element("div", "trajectory-step");
    append(step, element("div", "step-label", index === 0 ? "body before" : `step ${index}`), bodyBars(bodyState));
    append(wrapper, step);
  });
  append(wrapper, rawDetails("Inspect exact rollout", rollout));
  return wrapper;
}

function renderInstinktPanel(payload) {
  const panel = els.panels.instinkt;
  panel.replaceChildren();
  if (!payload) {
    append(panel, panelHeading("Instinkt", "Run an explicit deterministic cycle to inspect cue evidence and body trajectories."));
    append(panel, emptyNotice("No cycle yet", "Bootstrap does not infer body effects or start a processor."));
    return;
  }
  const instinkt = asObject(payload);
  const policy = asObject(instinkt.policy);
  const abstention = asObject(instinkt.abstention);
  append(
    panel,
    panelHeading(
      "Instinkt",
      "Cue provenance, predicted effects, memory associations, and virtual body trajectories remain inspectable.",
      policy.status || "native"
    )
  );
  const statusStrip = element("div", "status-strip");
  append(
    statusStrip,
    statusPill("policy", policy.status),
    statusPill("abstained", abstention.abstained),
    statusPill("native abstains", instinkt.conclusion?.abstains),
    statusPill("effect source", instinkt.effect_status?.source),
    statusPill("prediction", instinkt.effect_status?.prediction_status),
    statusPill("dominant alarm", instinkt.dominant_alarm),
    statusPill("native option", instinkt.conclusion?.option_id)
  );
  append(
    panel,
    statusStrip,
    fieldGroup("Native uncertainty", instinkt.conclusion?.uncertainty)
  );

  const bodySection = element("section", "subsection");
  append(bodySection, subsectionTitle("Body before / body after", "13 bounded dimensions"));
  const bodyGrid = element("div", "body-comparison-grid");
  for (const [title, value] of [["Body before", instinkt.body_before], ["Body after", instinkt.body_after]]) {
    const bodyCard = card(title);
    append(bodyCard, value ? bodyBars(value) : emptyNotice("No body state", "The policy abstained or no decisive trajectory exists."), rawDetails(`Inspect ${title.toLowerCase()}`, value));
    append(bodyGrid, bodyCard);
  }
  append(bodySection, bodyGrid);
  append(panel, bodySection);

  const cueSection = element("section", "subsection");
  const cues = asArray(instinkt.cue_evidence);
  append(cueSection, subsectionTitle("Cue evidence", `${cues.length} provenance binding${cues.length === 1 ? "" : "s"}`));
  const cueGrid = element("div", "panel-grid two");
  for (const cue of cues) {
    const cueCard = card(humanize(cue.lane || cue.cue_lane || "cue evidence"));
    append(
      cueCard,
      choiceLine("Cue", cue.cue || cue.cue_text || cue.normalized_cue),
      fieldGroup("Evidence IDs", cue.evidence_ids, { asChips: true }),
      rawDetails("Inspect cue binding", cue)
    );
    append(cueGrid, cueCard);
  }
  if (!cues.length) append(cueGrid, emptyNotice("No automatic cue bindings", "This cycle may use explicit manual fixture effects."));
  append(cueSection, cueGrid);
  append(panel, cueSection);

  const predictionsSection = element("section", "subsection");
  const predictions = asArray(instinkt.predicted_body_effects);
  append(predictionsSection, subsectionTitle("Predicted body effects", `${predictions.length} option prediction${predictions.length === 1 ? "" : "s"}`));
  const predictionGrid = element("div", "panel-grid two");
  for (const prediction of predictions) {
    const predictionCard = card(prediction.option_id || "Option prediction");
    append(
      predictionCard,
      statusPill("abstains", prediction.abstains),
      fieldGroup("Uncertainty", prediction.uncertainty),
      fieldGroup("Body deltas", asArray(prediction.combined_deltas).map((item) => `${humanize(item.dimension)} ${display(item.delta)}`), { asChips: true }),
      fieldGroup("Unsupported dimensions", prediction.unsupported_dimensions, { asChips: true }),
      fieldGroup("Conflict flags", prediction.conflict_flags, { asChips: true }),
      fieldGroup("Cue evidence", asArray(prediction.evidence).map((item) => item.evidence_id), { asChips: true }),
      rawDetails("Inspect prediction and provenance", prediction)
    );
    append(predictionGrid, predictionCard);
  }
  if (!predictions.length) append(predictionGrid, emptyNotice("No rule-based prediction in this cycle", "No default body effect is invented when the manual fixture path is active."));
  const compilations = asArray(instinkt.effect_compilations);
  append(predictionsSection, subsectionTitle("Effect compilations", `${compilations.length} lineage wrapper${compilations.length === 1 ? "" : "s"}`));
  const compilationGrid = element("div", "panel-grid two");
  for (const compilation of compilations) {
    const compilationCard = card(compactId(compilation.compilation_id));
    append(
      compilationCard,
      keyValues([
        ["Source prediction", compilation.source_prediction_id],
        ["Ruleset", compilation.ruleset_id],
        ["Compiler", compilation.compiler_id],
        ["Revision", compilation.compiler_revision],
        ["Option", compilation.option_body_effect?.option_id],
      ]),
      rawDetails("Inspect effect compilation", compilation)
    );
    append(compilationGrid, compilationCard);
  }
  if (!compilations.length) append(compilationGrid, emptyNotice("No compiled prediction", "The active manual-fixture path supplied option effects without inventing a rule-based compilation."));
  append(predictionsSection, compilationGrid, rawDetails("Inspect manual option effects", instinkt.manual_option_effects));
  append(panel, predictionsSection);

  const associationSection = element("section", "subsection");
  const associationRecords = asArray(instinkt.association_matches);
  const matchCount = associationRecords.reduce((count, record) => count + asArray(record.matches).length, 0);
  append(associationSection, subsectionTitle("Association matches", `${associationRecords.length} option record${associationRecords.length === 1 ? "" : "s"} · ${matchCount} admitted match${matchCount === 1 ? "" : "es"}`));
  const associationGrid = element("div", "panel-grid two");
  for (const record of associationRecords) {
    const recordCard = card(record.option_id || "Option associations");
    const optionMatches = asArray(record.matches);
    if (!optionMatches.length) {
      append(recordCard, emptyNotice("No admitted association", "Bounded retrieval returned no memory record for this option."));
    }
    for (const match of optionMatches) {
      const matchItem = element("div", "route-item");
      append(
        matchItem,
        choiceLine("Match", compactId(match.match_id)),
        keyValues([
          ["Source kind", match.source_record_kind || "experienced_association"],
          ["Retrieval score", match.retrieval_score],
          ["Effective strength", match.effective_strength],
          ["Protected target", match.protected_target],
        ]),
        fieldGroup("Overlap tokens", match.overlap_tokens, { asChips: true }),
        rawDetails("Inspect admitted match", match)
      );
      append(recordCard, matchItem);
    }
    append(recordCard, rawDetails("Inspect option retrieval record", record));
    append(associationGrid, recordCard);
  }
  if (!associationRecords.length) append(associationGrid, emptyNotice("No association retrieval", "No bounded retrieval record was produced for this cycle."));
  append(associationSection, associationGrid);
  append(panel, associationSection);

  const rolloutSection = element("section", "subsection");
  const rollouts = asArray(instinkt.rollouts);
  append(rolloutSection, subsectionTitle("Option trajectories", `${rollouts.length} rollout${rollouts.length === 1 ? "" : "s"}`));
  for (const rollout of rollouts) append(rolloutSection, renderRollout(rollout, instinkt.conclusion?.decisive_rollout_id));
  append(
    rolloutSection,
    fieldGroup("Abstention and uncertainty", asArray(abstention.uncertainty_by_option).map((item) => `${item.option_id}: ${item.uncertainty}${item.abstains ? " (abstained)" : ""}`), { asChips: true }),
    rawDetails("Inspect policy", policy)
  );
  append(panel, rolloutSection, rawDetails("Inspect complete Instinkt panel", instinkt));
}

function renderCharacterPanel(payload) {
  const panel = els.panels.character;
  panel.replaceChildren();
  if (!payload) {
    append(panel, panelHeading("Character authority", "Run a cycle to inspect structural governance without diagnosing a person."));
    append(panel, emptyNotice("No cycle yet", "The profile selector is an explicit simulation input, not a diagnosis."));
    return;
  }
  const character = asObject(payload);
  const structural = asObject(character.structural_profile);
  const effective = asObject(character.effective_authority);
  const mandate = asObject(character.governance_mandate);
  const decision = asObject(character.conscious_decision);
  const behavior = asObject(character.behavior_resultant);
  append(panel, panelHeading("Character authority", "Stable structure selects governance; it is never inferred from behavior.", structural.profile_id || ""));

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
    fieldGroup("Effective tiers", asArray(effective.effective_tiers).map((tier) => asArray(tier).join(" = ")), { asChips: true }),
    rawDetails("Inspect authority", { structural, effective })
  );

  const availabilityCard = card("Processor availability");
  const availability = asObject(character.processor_availability);
  const availabilityScores = asObject(availability.scores);
  const unavailable = new Set(asArray(availability.unavailable_minds));
  const availabilityList = element("div", "availability-list");
  for (const mind of ["R", "E", "I"]) {
    const row = element("div", "availability-row");
    const value = availability.explicit && Object.hasOwn(availabilityScores, mind)
      ? availabilityScores[mind]
      : unavailable.has(mind) ? "unavailable" : "retained · not explicitly measured";
    append(row, element("span", "", mind), element("output", "", display(value)));
    append(availabilityList, row);
  }
  append(
    availabilityCard,
    availabilityList,
    fieldGroup("Availability basis", availability.status || (effective.functional_override ? "explicit functional override" : "no explicit unavailability · all retained")),
    rawDetails("Inspect availability evidence", effective.functional_override)
  );
  append(overview, authorityCard, availabilityCard);
  append(panel, overview);

  const governanceSection = element("div", "subsection");
  append(governanceSection, subsectionTitle("Governance resolution", display(mandate.status)));
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
  const majority = asObject(character.thirteenth_majority);
  const agreeingMinds = asArray(majority.agreeing_minds);
  const majoritySummary = majority.applicable
    ? `${display(majority.winning_option_id)} · ${agreeingMinds.length}/3 (${agreeingMinds.join(", ")})`
    : "not applicable";
  append(
    conflictCard,
    keyValues([["Pair conflict", character.pair_conflict ? "present" : "none"], ["13th majority", majoritySummary]]),
    rawDetails("Inspect pair conflict", character.pair_conflict),
    rawDetails("Inspect 13th majority", character.thirteenth_majority)
  );
  append(governanceGrid, mandateCard, conflictCard);
  append(governanceSection, governanceGrid);
  append(panel, governanceSection);

  const chainSection = element("div", "subsection");
  append(chainSection, subsectionTitle("Mandate → conscious decision → behavior", "three distinct records"));
  const chain = element("div", "decision-chain");
  for (const [label, item, option, status] of [
    ["Governance mandate", mandate, mandate.option_id, mandate.status],
    ["Conscious decision", decision, decision.option_id, decision.decision_status],
    ["Behavior resultant", behavior, behavior.option_id, behavior.status],
  ]) {
    const node = element("article", "decision-node");
    append(node, element("span", "", label), element("strong", "", display(option)), element("p", "", humanize(status)), rawDetails(`Inspect ${label.toLowerCase()}`, item));
    append(chain, node);
  }
  append(chainSection, chain);
  append(panel, chainSection);
}

function renderEgoEvent(event, index, total) {
  const payload = asObject(event.event);
  const kind = event.event_kind || event.kind || "measure";
  const details = element("details", "timeline-event-card");
  details.open = index === total - 1;
  const summary = element("summary", "timeline-event-summary");
  append(summary, element("span", "event-index", String(index + 1).padStart(2, "0")), element("strong", "", humanize(kind)), element("code", "", compactId(event.event_id || payload.measure_id || payload.correction_id)));
  append(details, summary);
  if (kind === "measure") {
    const decision = asObject(payload.conscious_decision);
    const behavior = asObject(payload.behavior_resultant);
    const outcome = payload.outcome;
    const overview = element("div", "timeline-event-grid");
    const decisionCard = card("Conscious decision");
    append(
      decisionCard,
      choiceLine("Option", decision.option_id),
      choiceLine("Made by", decision.made_by),
      fieldGroup("Reason", decision.reason || decision.explanation),
      rawDetails("Inspect decision", decision)
    );
    const outcomeCard = card("Behavior and outcome");
    append(
      outcomeCard,
      choiceLine("Behavior option", behavior.option_id),
      choiceLine("Behavior status", behavior.status),
      choiceLine("Outcome", outcome?.outcome_kind || outcome?.status || (outcome ? "recorded" : "not recorded")),
      rawDetails("Inspect behavior", behavior),
      rawDetails("Inspect outcome", outcome)
    );
    append(overview, decisionCard, outcomeCard);
    append(
      details,
      overview,
      fieldGroup("Translation gaps", asArray(payload.translation_gaps).map((gap) => `${gap.source_mind}: ${humanize(gap.distortion_type || gap.gap_status)}`), { asChips: true }),
      fieldGroup("Unresolved tensions", payload.unresolved_tensions, { asChips: true }),
      fieldGroup("Realization", englishRuntimeValue(payload.spoznanje_status)),
      rawDetails("Inspect complete EgoMeasure", payload)
    );
  } else {
    append(details, keyValues(Object.entries(payload).filter(([, value]) => typeof value !== "object").slice(0, 10).map(([key, value]) => [humanize(key), value])), rawDetails("Inspect correction event", payload));
  }
  return details;
}

function renderProjection(title, className, projection = {}, fields = []) {
  const wrapper = element("article", `projection-card ${className}`);
  append(wrapper, element("h3", "", title), choiceLine("Projection ID", compactId(projection?.projection_id)));
  for (const field of fields) append(wrapper, fieldGroup(humanize(field), projection?.[field], { asChips: true }));
  append(wrapper, rawDetails("Inspect exact projection", projection));
  return wrapper;
}

function renderEgoPanel(payload) {
  const panel = els.panels.ego;
  panel.replaceChildren();
  if (!payload) {
    append(panel, panelHeading("Ego Timeline", "Run explicit cycles to build one session-scoped longitudinal trace."));
    append(panel, emptyNotice("No measures yet", `This browser session will retain Ego ID ${state.sessionEgoId}; bootstrap never runs a cycle.`));
    return;
  }
  const ego = asObject(payload);
  const snapshot = asObject(ego.composition_snapshot);
  const measure = asObject(ego.measure);
  const narrative = asObject(ego.self_narrative);
  const projections = asObject(ego.projections);
  const timelineEvents = asArray(ego.timeline);
  append(
    panel,
    panelHeading(
      "Ego Timeline",
      "Ordered measures preserve decisions, outcomes, translation errors, tensions, realizations, self-narrative, and modality projections.",
      `${timelineEvents.length} event${timelineEvents.length === 1 ? "" : "s"}`
    )
  );
  const sessionStrip = element("div", "status-strip");
  append(sessionStrip, statusPill("session ego", state.result?.run?.ego_id || state.sessionEgoId), statusPill("current measure", measure.measure_id), statusPill("events", timelineEvents.length));
  append(panel, sessionStrip);

  const timelineSection = element("section", "subsection");
  append(timelineSection, subsectionTitle("Measures, decisions, and outcomes", "append-only event order"));
  const timeline = element("div", "expanded-timeline");
  timelineEvents.forEach((event, index) => append(timeline, renderEgoEvent(event, index, timelineEvents.length)));
  append(timelineSection, timeline);
  append(panel, timelineSection);

  const compositionGrid = element("div", "ego-grid");
  const compositionCard = card("Composition snapshot");
  append(
    compositionCard,
    fieldGroup("Identity motifs", snapshot.identity_motifs, { asChips: true }),
    fieldGroup("Recurring conflicts", snapshot.recurring_conflicts, { asChips: true }),
    fieldGroup("Translation errors", snapshot.recurring_translation_errors, { asChips: true }),
    fieldGroup("Unresolved tensions", snapshot.unresolved_tensions, { asChips: true }),
    fieldGroup("Resolved tensions", snapshot.resolved_tensions, { asChips: true }),
    fieldGroup("Realizations", englishRuntimeValue(snapshot.spoznanja), { asChips: true }),
    rawDetails("Inspect composition snapshot", snapshot),
    rawDetails("Inspect sourced claims", snapshot.sourced_claims)
  );
  const narrativeCard = card("Racio self-narrative");
  append(
    narrativeCard,
    fieldGroup("Claimed motive", narrative.claimed_motive),
    fieldGroup("Explanation", narrative.explanation),
    fieldGroup("Acknowledged minds", narrative.acknowledged_minds, { asChips: true }),
    fieldGroup("Omitted minds", narrative.omitted_minds, { asChips: true }),
    fieldGroup("Narrative uncertainty", narrative.uncertainty),
    rawDetails("Inspect self-narrative", narrative)
  );
  append(compositionGrid, compositionCard, narrativeCard);
  append(panel, compositionGrid);

  const projectionSection = element("section", "subsection");
  append(projectionSection, subsectionTitle("R / E / I projected histories", "same trace · modality-specific learning"));
  const projectionGrid = element("div", "projection-grid");
  append(
    projectionGrid,
    renderProjection("Racio projection", "racio", projections.racio, ["facts", "chronology", "causal_links", "commitments"]),
    renderProjection("Emocio projection", "emocio", projections.emocio, ["recurring_scenes", "desire_motifs", "rupture_motifs", "belonging_motifs"]),
    renderProjection("Instinkt projection", "instinkt", projections.instinkt, ["dangers", "losses", "recovery_patterns", "boundary_patterns", "trust_patterns"])
  );
  append(projectionSection, projectionGrid);
  append(panel, projectionSection, rawDetails("Inspect current EgoMeasure", measure));
}

function renderRuntimePanels() {
  const panels = state.result?.panels || {};
  renderRacioPanel(panels.racio);
  renderEmocioPanel(panels.emocio);
  renderInstinktPanel(panels.instinkt);
  renderCharacterPanel(panels.character);
  renderEgoPanel(panels.ego);
  if (!state.result) return;
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
  request.run_id = `gui-${randomToken()}`;
  request.ego_id = state.sessionEgoId;
  request.started_at = new Date().toISOString();
  const profileId = els.profileSelect.value;
  const contract = profileContracts().find((item) => (typeof item === "string" ? item : item.profile_id) === profileId);
  if (contract && typeof contract === "object") {
    request.character = { ...request.character, profile_id: contract.profile_id, authority_tiers: contract.authority_tiers, rule: contract.rule };
  }
  return request;
}

async function runCycle() {
  if (state.busy) return;
  const debugRequested = els.debugToggle.checked;
  state.busy = true;
  els.runCycleBtn.disabled = true;
  els.profileSelect.disabled = true;
  els.debugToggle.disabled = true;
  setRuntime("Running native cycle…", `Session Ego ${compactId(state.sessionEgoId)} · deterministic providers`, "working");
  try {
    const request = buildCycleRequest();
    const completed = await apiJson(`/api/cycles?debug=${debugRequested ? "true" : "false"}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    state.result = completed;
    if (!debugRequested || !els.debugToggle.checked) {
      redactEvaluatorState();
    }
    renderRuntimePanels();
    if (state.shadowEvidence) {
      setRuntime(
        "Reviewing frozen shadow evidence",
        `Deterministic cycle complete · ${state.result.run?.profile_id || request.character.profile_id} · No model call will be made`,
        "ok"
      );
    } else {
      setRuntime("Cycle complete", `${state.result.run?.profile_id || request.character.profile_id} · Ego trace ${state.result.panels?.ego?.timeline?.length || 1}`, "ok");
    }
  } catch (error) {
    console.error(error);
    setRuntime("Cycle failed", error.message, "error");
  } finally {
    state.busy = false;
    els.runCycleBtn.disabled = false;
    els.profileSelect.disabled = false;
    els.debugToggle.disabled = false;
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
  const [runtimeResult, labResult, shadowRegistryResult] = await Promise.allSettled([
    apiJson("/api/bootstrap"),
    apiJson("/api/semantic-lab"),
    apiJson("/api/shadow-evidence"),
  ]);
  if (runtimeResult.status === "rejected") {
    console.error(runtimeResult.reason);
    setRuntime("Bootstrap failed", runtimeResult.reason.message, "error");
    els.sceneSummary.textContent = runtimeResult.reason.message;
    state.labError = labResult.status === "rejected" ? labResult.reason.message : null;
    if (labResult.status === "fulfilled") state.lab = labResult.value;
    if (shadowRegistryResult.status === "fulfilled") {
      state.shadowRegistry = shadowRegistryResult.value;
    } else {
      state.shadowRegistryError = shadowRegistryResult.reason.message;
    }
    renderSemanticPanel();
    renderRuntimePanels();
    return;
  }
  state.bootstrap = runtimeResult.value;
  if (labResult.status === "fulfilled") {
    state.lab = labResult.value;
  } else {
    state.labError = labResult.reason.message;
    console.error(labResult.reason);
  }
  if (shadowRegistryResult.status === "fulfilled") {
    state.shadowRegistry = shadowRegistryResult.value;
    const registeredDefault = state.shadowRegistry?.default_evidence_id;
    if (registeredDefault) state.selectedShadowEvidenceId = registeredDefault;
  } else {
    state.shadowRegistryError = shadowRegistryResult.reason.message;
    console.error(shadowRegistryResult.reason);
  }
  const request = templateRequest();
  if (!request) throw new Error("Missing deterministic request fixture.");
  loadProfiles();
  els.sceneSummary.textContent = request.scene?.raw_input || "Deterministic native cycle";
  els.sceneId.textContent = `scene ${compactId(request.scene?.event_id)}`;
  els.runId.textContent = `session ${compactId(state.sessionEgoId)}`;
  els.runCycleBtn.disabled = false;
  if (!state.shadowRegistryError && shadowRegistryEntries().length) {
    await loadShadowEvidence(state.selectedShadowEvidenceId, {
      announce: false,
      render: false,
    });
  }
  renderSemanticPanel();
  renderRuntimePanels();
  const familyCount = semanticFamilies().length;
  if (state.shadowEvidence) {
    setRuntime(
      "Reviewing frozen shadow evidence",
      "No model call will be made",
      "ok"
    );
  } else if (state.labError) {
    setRuntime(
      "Runtime ready · Semantic Lab unavailable",
      `${state.labError} · deterministic cycle idle`,
      "error"
    );
  } else {
    setRuntime("Ready", `${familyCount} semantic families · deterministic cycle idle · no hidden model calls`, "ok");
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
els.debugToggle.addEventListener("change", async () => {
  if (!els.debugToggle.checked) {
    redactEvaluatorState();
    redactShadowEvaluatorState();
  }
  renderRuntimePanels();
  if (state.selectedShadowEvidenceId) {
    await loadShadowEvidence(state.selectedShadowEvidenceId, {
      announce: false,
    });
  }
});
activatePanel("semantic");
bootstrap().catch((error) => {
  console.error(error);
  setRuntime("Bootstrap failed", error.message, "error");
  state.labError ||= error.message;
  renderSemanticPanel();
});
