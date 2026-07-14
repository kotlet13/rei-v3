# C4 visual-cognition runtime integration acceptance — 2026-07-14

## Outcome

**TECHNICAL C4 RUNTIME INTEGRATION PASSED; THE SEMANTIC MODEL QUALITY GATE
REMAINS OPEN.**

The C4 runtime is integrated directly in `main`. It now closes the configured
Emocio processing path from immutable runtime configuration through renderer
and encoder calls, visual valuation, native conclusion, engine assembly,
durable binary materialization and cold replay.

This acceptance does not approve the current renderer candidate for native
visual influence. The pinned FLUX.2 Klein smoke remained semantically unstable,
and the pinned DINOv2 valuation correctly refused fusion after detecting action
collapse. The repository visual-influence authority registry therefore remains
deliberately empty.

## Git closure

| Field | Exact value |
|---|---|
| branch | `main` |
| C4 base | `7451cacbc635151dd5623370609cbc0e516518d0` |
| accepted head | `2d9948d7e4df0ac8a16702a7c1079b1bae067333` |
| remote | `origin/main` |
| post-push divergence | `0` ahead, `0` behind |
| development rule | direct commits on `main`; no C4 feature branch |

Integrated C4 commits, in order:

| Commit | Scope |
|---|---|
| `a4b5388` | pin visual candidates and the main-only workflow |
| `d671796` | add explicit visual-cognition contracts |
| `b849008` | add the provenance-closed current-first renderer |
| `983c691` | add pinned encoding and provenance-closed visual valuation |
| `a625200` | integrate visual cognition into the deterministic Emocio path |
| `2d9948d` | close configured engine execution, persistence and cold replay |

## Accepted technical scope

The integrated runtime provides:

- exact `structured_only`, `render_observe` and `visual_cognition` modes;
- immutable, content-addressed processor configuration and processing result
  artifacts;
- exact renderer identity, prompt profile, seed, request and provider-call
  closure;
- exact image-encoder identity, snapshot pin, request and provider-call
  closure;
- current-first rollout source binding and generated-only epistemic boundaries;
- stage-aware visual policy, approval and repository-pinned authority lineage;
- fixed, redacted failure codes and messages that do not persist exception
  classes, provider secrets or local paths;
- a single aggregate outer deadline plus cooperative renderer and encoder
  deadlines;
- canonical capture of provider execution before downstream assembly, closing
  stateful-property and time-of-check/time-of-use substitutions;
- pre-downstream validation before governance, C3 interpretation or Ego CAS;
- exact provider call ordering in `RunManifest`;
- durable PNG and float32-vector snapshots with hash, dimensions, path, role and
  byte-level replay checks;
- exact `emocio/images/` and `emocio/embeddings/` namespace closure, rejecting
  inventoried orphan binaries without renderer or encoder provenance;
- restart-safe replay of duplicated packet, state, scene, image-index and native
  conclusion views;
- continued compatibility with the pre-C4 structured-only provider shape.

The `structured_only` path remains the reference baseline. `render_observe`
cannot change the native conclusion. `visual_cognition` can affect it only
through the explicit valuation, approval and repository trust-root path.

## Verification

The final focused regression command covered contracts, runtime, engine,
providers, prompting, renderer, timeout, current-first rendering, visual
integration, DINOv2 and C3 compatibility:

```powershell
app\backend\.venv\Scripts\python.exe -m pytest -q `
  tests/rei/test_emocio_c4_contracts.py `
  tests/rei/test_emocio_runtime.py `
  tests/rei/test_emocio_engine_integration.py `
  tests/rei/test_deterministic_providers.py `
  tests/rei/test_emocio_prompting.py `
  tests/rei/test_emocio_renderer.py `
  tests/rei/test_emocio_renderer_timeout.py `
  tests/rei/test_emocio_current_first_renderer.py `
  tests/rei/test_emocio_visual_integration.py `
  tests/rei/test_emocio_dinov2_encoder.py `
  tests/rei/test_engine.py `
  tests/rei/test_c3_engine_integration.py
```

Result: **128 passed**.

The complete REI regression suite was then run:

```powershell
app\backend\.venv\Scripts\python.exe -m pytest -q tests/rei
```

Result: **825 passed**.

Additional closure checks:

- `python -m compileall -q app/backend/rei tests/rei`: passed;
- staged `git diff --check`: passed;
- the renderer-module reload followed by the full DINOv2 suite: 23 passed;
- final security review: no remaining P1/P2 findings;
- final code review: no remaining P1/P2 findings.

The reload regression exposed a class-identity-only comparison after
`importlib.reload`. Snapshot manifests are now compared through their exact
canonical bytes, preserving the byte-integrity guarantee across reloads.

## Model-backed evidence and refusal

The technical renderer evidence is recorded in
[`c4_renderer_smoke_2026-07-14.md`](./c4_renderer_smoke_2026-07-14.md).
Its pinned offline batch completed with full image and call provenance, but
human review rejected the candidate for semantic rollout use because subject
preservation and option-action separation were not stable together.

The encoder and valuation evidence is recorded in
[`c4_dinov2_visual_valuation_smoke_2026-07-14.md`](./c4_dinov2_visual_valuation_smoke_2026-07-14.md).
DINOv2 produced provenance-closed vectors, measured rollout separation of only
`0.008770679567`, emitted `review_action_collapse` and refused visual fusion.
That refusal is the expected fail-closed outcome.

Candidate-selection constraints remain recorded in
[`c4_visual_model_selection_2026-07-14.md`](./c4_visual_model_selection_2026-07-14.md).

## Open quality gate and limitations

The following work is not accepted by this report:

- semantic stability across three seeds, two styles, both prompt languages,
  option-order permutations and another renderer;
- a renderer candidate that preserves the source subject while producing
  reliably distinct option actions;
- repository pinning of a production visual-influence approval or authority;
- hard cancellation of a blocked CUDA kernel;
- protection against a same-credential writer that transiently swaps trusted
  local model bytes and restores them before post-inference verification.

Until those requirements pass a scoped review, generated imagery may remain an
internal observation but cannot receive repository-authorized native influence
in production.

## Decision and next step

C4's technical runtime, provenance and replay layer is accepted at
`2d9948d`. The semantic model quality gate is explicitly not accepted. C5 has
not started and requires a separate user review and instruction.

Rollback is a normal reverse-order revert of the scoped C4 commits on `main`;
no history rewrite, force-push or branch recreation is required.
