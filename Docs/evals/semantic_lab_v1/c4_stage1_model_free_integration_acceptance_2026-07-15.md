# C4 Stage 1 model-free integration acceptance — 2026-07-15

## Outcome

**THE C4 STAGE 1 PRE-INFERENCE BOUNDARY IS INTEGRATED ON `main`; NO IMAGE
MODEL OR DINOV2 MODEL WAS LOADED OR CALLED, NO HUMAN REVIEW WAS PERFORMED,
AND NO SEMANTIC OR PRODUCTION AUTHORITY IS GRANTED.**

Implementation commit `5c39c6abba7f70a07502b975e34d03cc16b97ee3c`
adds the exact provider, snapshot, execution, telemetry, publication, DINO and
display/review boundaries. Follow-up commit
`e04e21f00fc0322d8b64fa096a51042ee02022ed` pins the ordinary-file Git for
Windows entry point after the live repository gate correctly rejected Git's
hard-linked `cmd/git.exe` wrapper. Both commits were pushed directly to
`origin/main` before this acceptance record.

The final live repository gate passed with `main`, local `origin/main` and the
remote `refs/heads/main` all equal to `e04e21f00fc0322d8b64fa096a51042ee02022ed`,
the complete controlling C4 scope clean, and the trusted Git location recorded
as `windows-program-files-git-bin`.

This phase satisfies the model-free integration requirement in
[`c4_stage1_model_free_integration_addendum_2026-07-15.md`](./c4_stage1_model_free_integration_addendum_2026-07-15.md).
The first model-backed Stage 1 run remains a separate phase and requires review
of this acceptance plus a new copy-only external worker runtime.

## Phase record

```text
Phase: C4 controlled visual remediation — Stage 1 model-free integration
Branch: main
Base main SHA: a92ec9b190e41d9a79e3b59ecf06d9dd7e47eb3c
Head SHA: e04e21f00fc0322d8b64fa096a51042ee02022ed
Changed files: app/backend/rei/emocio/dinov2_encoder.py; app/backend/rei/evaluation/process_tree_runner.py; app/backend/rei/evaluation/resource_telemetry.py; app/backend/rei/persistence/artifacts.py; tests/evaluation/test_process_tree_runner.py; tests/evaluation/test_resource_telemetry.py; tests/rei/test_emocio_dinov2_encoder.py
New files: two exact snapshot manifests; one model-free addendum; three Stage 1 editor/provider modules; eight Stage 1 evaluation modules; three guarded execution scripts; twelve Stage 1 evaluation test modules; one Stage 1 editor test module
Deleted files: none
Architecture changes: content-addressed prepared-attempt anchor; exact provider/pipeline/snapshot/source/runtime pins; stdlib-only pre-site bootstrap and single-use worker capability; parent-owned execution and durable telemetry; atomic two-option member publication receipt; receipt-bound DINO and exact-byte display/review consumers
Runtime changes: guarded prepare-by-default CLI; explicit execute confirmation; isolated no-site worker launch; exact full worker/base runtime inventories; main/origin live gate; 180-second option and 420-second family limits; sampled whole-device CUDA stop above 31,500 MiB; create-only staging and publication; no model execution in this phase
Canon claims added: none
Implementation hypotheses added: exact LongCat Turbo and OmniGen Stage 1 adapters remain non-authoritative evaluation hypotheses; sampled telemetry, display attestation and provider-output limits remain explicit
Open questions added: actual two-family image quality; DINO separation; sealed human review; copy-only external runtime; later parent-side LongCat Lanczos derivation hardening
Tests run: 288-test focused C4/runner/telemetry/editor gate; all tests/evaluation; all tests/rei; tracked semantic-lab/archive/cutover tests; 80-test final persistence/preflight recheck; 35-test Git-runtime follow-up; Ruff; py_compile; import hygiene; inert-entrypoint check; live production repository gate; independent P0/P1/P2 audit
Tests passed: 288 focused; 442 evaluation; 1096 REI; 20 semantic-lab/archive/cutover; 80 persistence/preflight recheck; 35 Git-runtime follow-up; all static, import, live-gate and audit checks
Tests failed: 0 on final state
Model-backed runs: 0
Artifacts created: 30 repository files including complete snapshot manifests, contracts, guarded runners and adversarial tests; no generated candidate PNG, embedding, review or authority artifact
Known limitations: the existing UV renderer venv is intentionally rejected because it contains hardlinks and a base-runtime reparse point; a copy-only ordinary-file venv is required; sampled memory peaks remain lower bounds; cold receipts do not prove human attention or cognition; LongCat parent replay binds direct/staged hashes and policy but does not independently recompute Pillow Lanczos bytes; hostile concurrent filesystem mutation remains an operational trust boundary
Regression risk: process containment, telemetry finalization, exact artifact inventory, bootstrap/runtime activation, provider-output lineage and review receipt replay; covered by focused adversarial tests, full regression suites and an independent no-P0/P1/P2 audit
Rollback path: normal revert of e04e21f and 5c39c6a plus this documentation commit on main; no rebase, history rewrite, force-push, tag move or branch recreation
Proposed commit: feat(eval): add model-free C4 Stage 1 boundary; fix(eval): pin ordinary-file Git runtime for C4 gate
Recommended next phase: after explicit review, create and pin a copy-only external renderer venv, then execute only the frozen four-call Stage 1 model-backed screen
```

## Accepted pre-inference boundary

The accepted preparation path binds, before any output exists:

- both exact Hub revisions and complete canonical file manifests;
- the frozen source PNG, scene/profile/prompts, option order and seeds;
- every provider load, call and output-normalization parameter;
- protocol/addendum hashes, review commitments, DINO policy and sampled-memory
  policy;
- the exact repository commit on live remote `main` and a full clean
  controlling scope;
- the worker executable, dependency metadata and every ordinary file in the
  worker virtual environment and base runtime.

Preparation rejects symlinks, Windows reparse points, hardlinks, special
files, runtime customization modules, added or missing snapshot entries,
hidden Git worktree flags and any local/remote commit mismatch. Runtime paths
remain operator-supplied memory-only bindings and are not serialized.

The production repository gate was executed after both implementation commits
were pushed. It passed on the ordinary-file Git `bin` entry point; portable
Stage 1 artifacts store only its content identity and trusted location class,
not the machine-local path.

## Accepted execution and publication boundary

The guarded CLI prepares by default. Execution requires `--execute` plus exact
repetition of the prepared-attempt ID and prepared-anchor storage ID.

The parent launches only the stdlib bootstrap with `-I -S`. Before it adds
verified site-package and backend roots, the bootstrap rechecks raw argv,
environment and cwd commitments; the prepared ledger; Git/runtime/script,
source and snapshot bytes; and the full worker/base runtime inventories. It
never executes `.pth`, `sitecustomize` or `usercustomize`. The directly invoked
worker is inert; only the bootstrap can inject and consume its process-local
single-use capability.

Each post-intent path records all independently persistable process, zero or
sampled telemetry, worker-result and terminal evidence. Unknown storage side
effects fail exact inventory and cannot be laundered into a final anchor.
Timeout, containment uncertainty, telemetry failure or CUDA breach fails
closed. A family publishes neither option unless both options pass. The two
direct/staged candidate pairs become consumable only when one create-only
member receipt commits both together; partial files without that marker are
inert.

Cold replay rebinds every terminal and published candidate to the exact
prepared worker, request, launch envelope, telemetry intent, process record,
runtime provenance, provider pipeline, snapshot, output policy and PNG bytes.
The public DINO and display/review APIs consume only cold-verified prepared and
member storage descriptors. Display receipts embed the prepared anchor,
atomic member marker and both candidate descriptors, and sealing/evaluation
reverify that lineage from a fresh store.

## Verification evidence

Final model-free commands included:

```powershell
python -m pytest <16 focused C4/runner/telemetry/editor modules> -q -W error
# 288 passed

python -m pytest tests/evaluation -q -W error
# 442 passed

python -m pytest tests/rei -q -W error
# 1096 passed

python -m pytest tests/semantic_lab `
  tests/test_archive_boundary.py `
  tests/test_archive_integrity.py `
  tests/test_native_cutover.py -q -W error
# 20 passed
```

Additional final checks established:

- 34 scoped Python files compiled successfully;
- Ruff check passed for all 34 scoped Python files and format check passed for
  all 33 newly formatted files while preserving the legacy formatting of
  `artifacts.py` outside its 43-line functional diff;
- importing all 12 Stage 1 modules and three scripts in a fresh process left
  `torch`, `diffusers`, `transformers`, `accelerate` and `safetensors` absent;
- direct `-I -S` worker and incomplete bootstrap invocation each returned 64
  with no output;
- exact snapshot manifests reproduced 37 files / 29,322,428,829 bytes and 11
  files / 8,088,956,424 bytes with their frozen canonical SHA-256 values;
- no machine-local cache path, secret marker or authority-true assignment was
  present in the scoped diff;
- an independent current-tree audit reported no outstanding P0, P1 or P2.

## Explicit non-authority and next gate

This acceptance does not claim that either image editor is good enough. It
does not execute DINOv2, establish action separation, display images to a
reviewer or perform a sealed human review. Generated images remain internal
imagination artifacts and cannot become external evidence. Semantic and
production authority fields remain literal `false`.

The installed UV renderer environment is not eligible for the next phase: its
package tree contains hardlinks and its base prefix resolves through a reparse
point. Before any approved model call, create a new external Python 3.11 venv
from the ordinary versioned base interpreter with copied files and copy-mode
package installation, then let Stage 1 preparation inventory and pin it.

After review, the next run is limited to the frozen primary-then-alternate,
`enter_circle`-then-`remain_edge` sequence: exactly four provider calls, no
best-of-N, no fallback and no expansion on a failed family. That later phase
must separately record model, CUDA, DINO and human-review evidence.
