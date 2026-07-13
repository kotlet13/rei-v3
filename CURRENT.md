# Current Project State

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
