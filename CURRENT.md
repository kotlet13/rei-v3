# Current Project State

## Research reset status - 2026-07-17

- Architecture status: stable.
- Technical contract status: strong.
- Research quality status: blocked.
- Default model-backed RacioInterpreter: none.
- Visual native-influence authority: none.
- Emocio exploration:
  - LongCat is the selected promising renderer/editor.
  - ENTER was accepted in 2/3 reviewed roots.
  - English REMAIN was accepted in 3/3 reviewed roots.
  - No visual native-influence authority has been granted.
- RacioInterpreter:
  - The official Qwen pair remains `23/32 + 23/32` and is not accepted.
  - The X2 failure audit was human-reviewed with H3/H7/H11 amendments.
  - The epistemic output/evaluator v2 contract and pass-symmetry audit are in
    place without changing the frozen v1 contract.
  - The next and only new candidate in this cycle is `gemma4:31b` at exact
    digest `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7`.
  - The first G2 `/api/generate` probe lacked a separate thinking field. One
    explicitly authorized `/api/chat` endpoint probe then returned separate
    thinking/content and loaded at context `65536` and `100% GPU`, but its
    final content failed the strict v2 structured-output contract. Both probes
    failed closed, no retry or fallback was used, and G3 was not started.
  - After explicit diagnostic authorization, one `g2-chat-v3` probe on the
    reproducible provider test packet again failed as
    `structured_output_invalid`, now narrowed to one root `value_error`.
    Thinking separation, final-content presence, exact runtime, context
    `65536`, and `100% GPU` all passed; no retry or fallback was used.
  - A frozen v4 confirmation returned the same 387-byte final-response hash and
    identified `ambiguity_state_mismatch`. The validator requires a mechanical
    four-way mapping from option selection and motive count, while the v4
    prompt/schema exposed only the allowed ambiguity values, not that mapping.
  - Provider revision `g2-chat-v5` exposed the existing mapping explicitly in
    the instruction and schema description, but the correction experiment still
    produced the same 387-byte final response and the same invariant failure.
  - A final state-only diagnostic established the exact contradiction: the
    model selected an option and returned zero motive hypotheses, yet emitted
    the `option` ambiguity literal; that state mechanically requires `null`.
    The provider is correctly fail-closed. No raw thinking/final/envelope was
    persisted, calls/retries/fallbacks are `6/0/0`, and G3 remains unstarted.
  - A subsequent REI theory review superseded that mechanical v2 ambiguity
    contract without changing the historical diagnosis. Model-free provider
    revision `g2-chat-v6` now requires Racio-owned tri-state uncertainty reports
    (`uncertain`, `not_uncertain`, `not_reported`) that remain independent of
    option, motive count and confidence.
  - Response evidence v2 embeds the sanitized validated output and a
    cold-verifiable provider-derived sidecar containing only option-ID presence
    and motive-hypothesis count as derived facts. The sidecar is explicitly
    non-semantic, non-governance and excluded from evaluator scoring.
  - Duplicate JSON keys now fail closed at every object depth without leaking
    model content. This was a model-free correction: calls/retries/fallbacks
    remain `6/0/0`, G3 remains unstarted, and a new human gate is required
    before another Gemma call.
  - The explicitly authorized v6 confirmation at `num_predict=2048` produced
    separate thinking but no contract-acceptable final and failed as
    `generation_contract_failure` before JSON/Pydantic validation. It used one
    call with no retry or fallback.
  - The user then authorized a profile-only correction to
    `num_predict=16384`. The next and only call closed with `done_reason=stop`,
    passed strict structured-output and conscious-access validation, and
    created response evidence
    `gemma4_epistemic_response_b66ec431c6dcae651f18da3c046f3864` plus a
    successful `ProviderCallRecord`. Exact digest, context `65536`,
    `num_gpu=999`, and `100% GPU` placement were recorded.
  - The successful confirmation output and its Racio uncertainty self-report
    remain technical evidence only; they were not reused as G3 semantic gold.
  - After a separate explicit phase decision, the sealed G3 development screen
    completed exactly 16/16 Gemma calls over eight precommitted SL/EN roots.
    All calls produced validated outputs and successful `ProviderCallRecord`
    artifacts with retry `0`, fallback `none`, context `65536`, `num_gpu=999`,
    and recorded `100% GPU` placement.
  - G3's independent dimensions are mixed: structural contract `16/16`; action
    support `8/16`; all 12 unique options mapped and all four required
    abstentions were observed; 15 unsupported motive hypotheses occurred
    across 10 cases; motive confidence was within bound in `15/16`; action
    bilingual consistency was `3/8`; option consistency was `8/8`; Racio
    uncertainty self-report consistency was `7/8` and remains non-gating.
  - The complete report and sanitized evidence are in
    `Docs/evals/research_reset_2026-07/gemma4_racio_epistemic_dev_screen.md`
    and
    `Docs/evals/semantic_lab_v1/g3-gemma4-racio-epistemic-2026-07-17/`.
    No aggregate semantic pass/fail was computed, Gemma is not promoted, and
    runtime integration has not started. Cumulative
    calls/retries/fallbacks are `24/0/0`; stop for human review.
- Instinkt: transparent effect-rules engine; raw scene understanding remains
  open.
- Ego: append-only composition; untagged semantic motif detection remains
  open.

C3 has not been accepted for model quality. The official `qwen3.6:35b` pair
scored 23/32 on the holdout and 23/32 on the frozen regression corpus, without
a phase pass. The X2 audit is now human-reviewed, but it does not retroactively
change either result. C4's technical runtime is accepted, but its visual
semantic quality and native-influence authority are not. C5 and C6 are bounded
software contracts rather than evidence of autonomous Instinkt scene
understanding or untagged Ego motif understanding. C7 research quality remains
blocked, and C9 is not open.

Future research follows
`plans/REI_research_reset_human_signal_plan_2026-07-16.md`: feature branches,
human review between phases, exploration before validation, and no automatic
phase continuation.

As of 2026-07-13, the native REI composition architecture is the active
runtime. Phase B13 completed the breaking cutover from the transitional
packages to `app/backend/rei/` and `app/gui/`. Phase B14 owns the final
acceptance record at
`Docs/evals/rei_native_architecture_acceptance_2026-07-13.md`.

## Active execution boundary

- engine: `app.backend.rei.engine.ReiNativeEngine`
- deterministic cycle runner: `scripts/run_rei_native_cycle.py`
- governance matrix runner: `scripts/run_rei_native_profile_matrix.py`
- GUI server: `app.gui.server:app`
- run artifacts: `output/runs/{run_id}/`
- append-only Ego traces: `output/ego_traces/`
- native tests: `tests/rei/`
- immutable legacy archive:
  `archive/rei_v3_text_llm_baseline_2026-07-13/`

There is no active `rei_next` or `gui_next` package. Active code does not
import the archive. The old matrix runner, textual runtime, dataset-generation
entrypoints, prompt/dataset GUI, and duplicate tests exist only in the frozen
archive snapshot.

## Architecture contract

1. Racio, Emocio, and Instinkt receive profile-blind native inputs and conclude
   independently.
2. Emocio's structured visual world and Instinkt's virtual body are
   authoritative even when no optional raster renderer is enabled.
3. Racio interprets only observable manifestations; evaluator native truth is
   excluded from the conscious input and appears only in explicit debug views.
4. Character governance is ordinal. It does not use weighted-vote floats or an
   LLM tie-breaker.
5. Every conscious decision is Racio's. Governance mandate, conscious
   decision, and behavior resultant remain three distinct records.
6. Ego is an append-only measure/trace/composition history with sourced
   modality projections. Ego has no decision or vote API.
7. Run storage is create-only, content-addressed, manifest-closed, and
   cold-verifiable.

## Deterministic commands

```powershell
python scripts/run_rei_native_cycle.py `
  --runs-root output/runs `
  --ego-traces-root output/ego_traces

python scripts/run_rei_native_profile_matrix.py `
  --output output/reports/rei_native_profile_matrix.json

python -m uvicorn app.gui.server:app --host 127.0.0.1 --port 8765
```

The matrix is 12 frozen native bundles × 13 canonical profiles = 156 rows. It
executes governance and the downstream conscious/behavior path without
rerunning a native processor or model.

## Cutover evidence

The B13 verification on 2026-07-13 established:

- archive SHA-256 inventory and source identity: passed;
- promoted native core and cutover guards: 609 passed;
- literal full worktree suite, including the user's unstaged v2 tests:
  622 passed;
- deterministic end-to-end cycle: all invariants passed, 45 stored artifacts;
- canonical profile matrix: 156 rows, 12 fixtures, 13 profiles;
- Edge GUI smoke: all four panels, explicit debug boundary, `R=E=I` majority
  display, no horizontal overflow, no console warning/error.

## Model boundary

The active architecture contains strict model-provider protocols and optional
adapters, but deterministic execution remains the default. Exact real-provider
coverage, local Ollama/Granite observations, and integrations still missing
from the architecture are recorded by B14 rather than inferred here.

## Legacy and rollback

The old comparison baseline was the 13-profile × 12-scenario textual matrix
using `ReiEngine.run_rei_cycle`, Ollama, and `granite4.1:30b` with explicit
`num_ctx=65536` and `num_gpu=999`. Its source commit is
`05996b2b4a34cf6dd654e032d5dbc26bb5373ef0`; the behavior-bearing ancestor is
`995b572c893058c82d265d978a0391e317f1ea67`.

The final B14 acceptance report provides the exact tag-based rollback command.
Do not import or modify files under the archive to implement active behavior.
