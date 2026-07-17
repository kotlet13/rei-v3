# Current Project State

## Research reset status - 2026-07-16

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
  - The next and only new candidate in this cycle is `gemma4:31b`.
  - The active phase is epistemic output v2 plus a bounded Gemma development
    screen.
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
