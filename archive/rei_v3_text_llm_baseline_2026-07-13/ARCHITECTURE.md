# Archived textual REI-v3 architecture

This document describes the source tree at
`05996b2b4a34cf6dd654e032d5dbc26bb5373ef0`. It preserves the system as a
productive research step that established contracts, fallbacks, diagnostic
tools, and a profile-sensitive evaluation baseline. It also records the limits
that motivated the later native-modalities redesign.

## Active cycle

The baseline runner calls `ReiEngine.run_rei_cycle` from
`app/backend/rei/engine.py`.

One cycle proceeds as follows:

1. `profile_weights` normalizes one of 13 character profiles into continuous
   Racio, Emocio, and Instinkt weights.
2. The engine creates deterministic fallback signals for all three minds.
3. With an enabled Ollama or LM Studio provider, it calls Racio, Emocio, and
   Instinkt sequentially and asks each for contract-shaped JSON.
4. All three processors receive the same textual scenario, normalized profile,
   and influence weights. They differ through processor-specific contracts,
   prompts, reference context, sampling settings, and potentially model
   selections; knowledge is therefore not literally identical across calls.
5. Provider or validation failures retain the deterministic signal. Missing
   required keys can trigger one JSON repair attempt.
6. `assess_acceptance` derives `AcceptanceAssessment` with deterministic
   keyword and regular-expression heuristics over the three textual signals.
7. The engine builds a deterministic `EgoResultant` fallback and, in LLM mode,
   attempts a separate EgoResultant LLM call.
8. The API returns `REICycleResponse`: three signals, acceptance, EgoResultant,
   and provider/fallback diagnostics.

The cycle therefore has three processor calls plus a separate synthesis call.
EgoResultant is a per-cycle synthesis layer in this architecture, not a
longitudinal append-only composition.

## Textual processor contracts

`models.py` defines a common `REISignal` and specialized Pydantic models:

- `RacioSignal` emphasizes facts, logic, unknowns, plans, and
  rationalization risk.
- `EmocioSignal` expresses desired and broken images, attention, status,
  attraction, pride/shame, and action tendency as text fields.
- `InstinktSignal` expresses threat maps, body alarms, loss, attachment,
  freeze/flight, resource exposure, and protective tendency as text fields.

The contracts preserve the distinction that Racio is conscious while Emocio
and Instinkt are exposed as translations by Racio. However, all three native
computations still use textual LLM requests; there is no frozen visual scene
process or virtual-body rollout before translation.

`contract_loader.py` and `prompts.py` load
`knowledge/canon/processor_contracts.json`, apply compact/full contract rules,
and provide required-key lists. `knowledge.py` exposes the structured
`knowledge/rei_knowledge_index.json`. Local GUI prompt overrides are outside
the tracked baseline and are deliberately excluded from the archive.

## Character profiles and resultant pressure

`profiles.py` supports 13 profile forms: three single leaders, three joint
leaders, six ordered profiles, and the balanced profile. Each is represented
by decimal weights.

The deterministic fallback computes mind pressure as:

```text
profile weight x signal confidence
```

It then adds `0.18` to a keyword-derived situational driver when one is found.
This allows situation and signal confidence to move the resultant away from
the nominal profile leader. The LLM EgoResultant contract likewise receives
the profile, weights, signals, and acceptance state and is post-coerced to
meet baseline contract rules.

The baseline keeps three related authority labels distinct:

- `profile_leader`: the nominal leader implied by the character profile;
- `situational_driver`: the mind activated by scenario-keyword heuristics;
- `resultant_leader_under_pressure`: the final pressure result after signal
  confidence and the optional situational bonus are applied.

## Acceptance

`acceptance.py` produces `AcceptanceAssessment` from textual cues. It derives
action tags, behavioral alignment, acceptance quality, return-loop, coalition,
and sabotage signals, including whether a step appears bounded or reversible.
This made acceptance observable and testable, but it also couples an
architectural concept mainly to English keyword/regex signals (with a smaller
Slovenian token set) and scenario phrasing.

## Providers and resilience

`providers.py` supplies:

- Ollama `/api/chat`, including streaming and environment-derived options;
- LM Studio chat support;
- JSON-object extraction and timing/token diagnostics.

The Ollama provider maps `REI_OLLAMA_NUM_CTX` to `num_ctx` and
`REI_OLLAMA_NUM_GPU` to `num_gpu`. On the baseline machine the known large-model
configuration used context `65536` and explicit `num_gpu=999`.

The engine's deterministic fallbacks, schema coercion, required-key checks,
and repair retry are important strengths: a malformed or unavailable model
does not automatically destroy a cycle, and failures remain visible in
diagnostics.

## Profile matrix

`scripts/run_rei_profile_matrix.py` defines 13 profiles and 12 scenarios,
yielding 156 cases. The scenarios cover meeting avoidance, job/business
change, public speaking, romantic return, coworker conflict, risky opportunity,
expensive purchase, grief, creative work, boundary violation, moral dilemma,
and family attachment.

For each case the runner records:

- fallbacks and missing contract keys;
- processor identity and textual distinctness;
- profile leader, situational driver, resultant, and leading mind;
- false-positive/false-negative heuristic flags and severity;
- action class, token counts, and provider diagnostics;
- profile sensitivity and unique Ego signatures in the aggregate summary.

Runtime files are `run.json`, `progress.log`, `cases.jsonl`, `cases.json`,
`summary.json`, and `summary.md`. A markdown summary is also copied to
`Docs/evals/rei_profile_matrix_summary_YYYY-MM-DD.md`. Because that filename
contains only a date, a filtered run can replace a full daily summary. The
2026-05-19 tracked summary has only 40 cases; the 2026-05-18 tracked summary is
the last clone-visible full 156-case record.

The deterministic provider exercises the fallback architecture without an
external model. It is useful for structural verification but does not reproduce
the semantics of the LLM path.

## GUI and dataset workbench

`app/gui/server.py` plus the static HTML/CSS/JavaScript workbench provides:

- side-by-side Racio, Emocio, Instinkt, and Ego output panels;
- prompt and provider/model parameter inspection;
- Ollama NDJSON streaming, stop signals, raw JSON, and local test history;
- dataset browsing, filtering, editing, approval/rejection, validation, and export.

The GUI calls Ollama directly and is not identical to the engine's
repair/fallback/coercion path. It is nevertheless valuable developer tooling
for prompt comparison and human review.

The active scripts also include generation, validation, export, and import of
fine-tuning/review datasets. The tracked profile-matrix review dataset contains
624 review-only examples derived from the 156-case matrix. The tracked pilot
dataset is a partial historical draft: 50 scenarios and 196 examples, with no
manifest at the source commit. These data artifacts are preserved as research
history, not as endorsement of the superseded QLoRA direction.

`engine.py` also retains the older `simulate()`/`SynthesisTurn` surface. No
active tracked runner uses it; the archived baseline boundary is
`run_rei_cycle` and the profile-matrix runner.

## Strengths retained as historical evidence

- Explicit processor contracts separated from prompt construction.
- Strict typed response schemas and canonical required-key validation.
- Provider diagnostics, one repair attempt, and graceful deterministic fallback.
- Ollama, LM Studio, and deterministic execution modes.
- A repeatable 13 x 12 matrix with rich profile-sensitivity diagnostics.
- A practical prompt and dataset review workbench.
- Evidence that profile-dependent textual synthesis can be measured and that
  three processor voices can be kept observably distinct.
- Concrete discovery of semantic and evaluator weaknesses that informed the
  next architecture.

## Known reasons for replacement

- Racio, Emocio, and Instinkt are all textual LLM processors over the same
  scenario type; Emocio is not a native visual world process and Instinkt is
  not a native embodied/homeostatic simulator.
- Character profile and decimal weights reach the processors themselves, so a
  processor conclusion cannot be reused as a profile-independent frozen bundle.
- Emocio and Instinkt do not commit immutable native conclusions before
  Racio's textual interpretation.
- Decimal weights, confidence, and a situational keyword bonus can alter
  authority rather than preserving stable ordinal character tiers.
- Acceptance is inferred from textual heuristics and can be influenced by cues
  such as “bounded” and “reversible”.
- EgoResultant adds a fourth LLM invocation for per-cycle synthesis even though
  its contract explicitly says it is not a fourth mind; it is not an
  append-only Ego trace or time-spanning composition.
- Model tags are recorded without immutable model digests/revisions or seeds,
  so live LLM outputs are not bit-for-bit reproducible.
- The sequential full matrix is expensive (at least 624 model calls before
  repair retries and roughly 1.5 million tokens in the last tracked full run).
- Runtime and evaluator heuristics share keyword concepts, limiting the
  independence of the evaluation.
- The GUI and baseline runner use different execution paths.

These limitations do not make the baseline a failed experiment. They are the
observations that made a clean architectural cut preferable to incremental
patching.
