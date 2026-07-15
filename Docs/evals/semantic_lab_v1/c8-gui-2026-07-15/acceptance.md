# C8 semantic native-process and longitudinal Ego GUI acceptance — 2026-07-15

## Outcome

**TECHNICALLY ACCEPTED AND INTEGRATED ON `main` BY THIS PHASE COMMIT.** C8
provides a read-only Semantic Lab browser and explicit Racio, Emocio, Instinkt,
Character and Ego workbench views. The phase was implemented directly on
`main` from `1d8c391bb8e60f02e0f7552463069c257699b9fc`; this report and the
plan status update are part of the same phase commit, so no self-referential
final SHA is embedded.

This is a technical GUI acceptance only. It does not change C7's research
disposition, select a production model, establish semantic quality, or grant
production authority. No model or image-provider call was made during C8.

## Delivered scope

Changed files:

- `app/backend/rei/persistence/artifacts.py`
- `app/gui/README.md`
- `app/gui/__init__.py`
- `app/gui/server.py`
- `app/gui/static/app.js`
- `app/gui/static/index.html`
- `app/gui/static/styles.css`
- `app/gui/view_model.py`
- `tests/rei/test_gui.py`
- `tests/rei/test_persistence.py`
- `plans/REI_next_phases_merge_semantic_architecture_2026-07-14.md`

New files:

- `app/gui/semantic_lab.py`
- `app/gui/storage.py`
- `tests/rei/test_gui_semantic_lab.py`
- `Docs/evals/semantic_lab_v1/c8-gui-2026-07-15/acceptance.md`

No file was deleted.

## Acceptance matrix

| C8 requirement | Disposition | Evidence boundary |
|---|---|---|
| Semantic Lab source, grounded scene, variant, expected/actual route, reviewer status, failure tags and Slovene/English comparison | PASS | Read-only `rei-semantic-lab-workbench-v1` projection exposes all 24 families and 192 variants; actual route remains absent and explicitly `not_executed` for the 180 variants without execution evidence. |
| Exact Racio-visible input | PASS | The normal view structurally omits evaluator ground truth, translation gaps and evaluator labels. |
| Local debug native truth, `TranslationGap` and evaluator label | PASS | Data is requested only with an explicit debug toggle; disabling it immediately redacts evaluator-only state before re-rendering. |
| Literal warning `Racio ground trutha ni prejel.` | PASS | Displayed in the Racio workbench. |
| Emocio current/desired/broken scenes, option rollouts, image and embedding lineage, structured/visual valuation, native option and renderer additions | PASS | The panel distinguishes structured and visual observations, keeps raw vectors out of the browser payload, identifies native abstention/options and labels ungrounded renderer additions. |
| Instinkt body before/after, cues, predicted effects, associations, trajectories, alarm and uncertainty | PASS | The panel keeps cue evidence, manual-fixture provenance, native abstention and native uncertainty explicit. |
| Ego measures, decisions, outcomes, motifs, translation errors, tensions, `spoznanja`, narrative and R/E/I projections | PASS | A stable per-browser-session Ego identity accumulates append-only measures across cycle runs and restart recovery, and renders the longitudinal composition separately from Racio self-narrative. |
| Character remains governance, not diagnosis | PASS | Character has a read-only authority/mandate view; no diagnosis action is present. |
| Loopback default, no automatic training export and no hidden model calls | PASS | Server policy is fail-closed by default, capability metadata declares the boundary, and C8 performs no export or provider activation. |
| C7 technical and research statuses remain separate | PASS | Technical `pass`, research `blocked`, semantic/production authority `false`, metric dispositions and blockers are rendered independently; no aggregate REI score is calculated or shown. |

## Architecture and data integrity

`app/gui/semantic_lab.py` introduces a bounded, read-only projection over the
checked-in C1 corpus, C2 evaluator evidence and C7 integrated benchmark. It
validates pinned manifest and artifact identities, rejects duplicate or
non-finite JSON values, bounds file reads, checks path/reparse/symlink and
time-of-check/time-of-use conditions, and verifies that each variant belongs to
its declared family. A single-flight gate prevents concurrent expensive
projection builds.

The projected C7 identity is:

```text
report_id: c7_integrated_benchmark_57c1db13906284edd641ac7cfbc6f5dc
report_hash: fb96308989974776e29fbe8c7e1e185211f77155d4726a453e1158b5a3c16adc
checked-in report file SHA-256: 64224a6c0e9615e7ff1981c334bc97182110014bcc77a1297bc272c311c47394
```

`rei-semantic-native-workbench-v2` expands the cycle view model without
collapsing processor boundaries. Normal Racio responses structurally exclude
evaluator-only truth. Emocio separates scene construction, visual observation
and valuation. Instinkt labels body evidence, provenance, abstention and
uncertainty. Ego retains distinct measures, narrative, motifs, tensions and
R/E/I projections.

Evaluator redaction covers the entire normal response, not only the current
Racio card: evaluator ground truth, labels and `TranslationGap` records are
removed from the current interpretation and the complete Ego composition and
measure history. The explicit local debug response is the only view that
contains that comparison evidence.

The browser uses text-only DOM construction for data values and has no HTML
injection sink. Initial page load performs read-only GET requests; a cycle is
created only after an explicit user action. The frontend generates a stable
session Ego ID and unique run IDs/timestamps for separate measures.

Longitudinal history is server-resolved; a browser cannot inject historical
bundles or modality signals. Run artifacts are partitioned under a
non-identifying SHA-256 namespace derived from `ego_id`. Recovery enumerates an
absolute maximum of 64 entries in that Ego partition, performs a bounded
traversal/reparse/TOCTOU-safe candidate read, matches expected bundle lineage,
and then treats a candidate as evidence only after full final- or
prepared-manifest verification. Native bundles are capped at 2 MiB before
persistence, so an accepted bundle cannot later exceed the recovery reader's
bound. A session is bounded to 30 measures. Duplicate bundle IDs, conflicting
lineage, unverified candidates, oversized partitions and ambiguous run
evidence fail closed.

`app/gui/storage.py` centralizes the existing canonical `sha256_hex(ego_id)`
derivation and strict 64-lowercase-hex URL validation, so raw, Unicode,
separator-bearing or Windows-device-like Ego IDs never become path segments.

## C7 status preserved without aggregation

The GUI reproduces, but does not reinterpret, the C7 disposition:

| C7 dimension | Status |
|---|---|
| Technical contract gate | PASS |
| Research-quality gate | BLOCKED |
| Semantic authority | NOT GRANTED |
| Production authority | NOT GRANTED |
| Current model calls | 0 |
| Historical C3 calls | 32, historical evidence only |
| Metric dispositions | 7 passed; 6 blocked; 3 observed; 1 not measured |

The five open blockers remain:

```text
c3_model_quality_gate_failed
c4_semantic_visual_gate_open
vlm_interpreter_arm_not_executed
semantic_motif_arm_not_executed
uniform_resource_telemetry_missing
```

There is no aggregate REI score, interaction score, implicit pass, or release
claim.

## Runtime and security boundary

The server adds the read-only `GET /api/semantic-lab` endpoint and expands the
bootstrap/cycle contracts. Synchronous cycle work is moved off the event loop;
both cycle execution and Semantic Lab projection are protected by bounded
single-flight gates and return an explicit retry response under contention.

Default access requires both a loopback socket client and a loopback `Host`.
Remote access is possible only through explicit environment opt-in, and remote
debug additionally requires its own opt-in. That remote mode is explicitly
documented as unauthenticated and suitable only for a trusted single-user
boundary: an `ego_id` is a namespace, not an authorization credential. The
server rejects cross-site fetches, mismatched `Origin`, untrusted host/proxy
combinations, non-JSON cycle
requests and oversized bodies. API responses are `no-store` and include a
self-only content-security policy, frame denial, MIME sniffing prevention,
same-origin resource policy, a restrictive permissions policy and no-referrer
policy.

Rendered PNGs are retrieved only through the Ego-partitioned
`/api/ego-runs/{partition_id}/{run_id}/images/{image_id}` route. The URL carries
only the canonical 64-hex partition digest, never the raw `ego_id`. The server
resolves that partition's artifact store, verifies the run reservation binds
back to the same Ego partition, then verifies the run manifest, image index,
digest, media signature and dimensions. It never accepts a free-form
filesystem path. Image lookups open `FileArtifactStore(create=False)`; a GET
for a missing partition returns not found without creating a directory or any
other filesystem state.

Independent code and security review found no remaining P0, P1 or P2 finding
after fixes for host/origin validation, content-type enforcement, event-loop
blocking, response headers, replay concurrency, family/variant binding,
stale-debug redaction and degraded bootstrap rendering.

## Validation performed

```powershell
app\backend\.venv\Scripts\python.exe -m pytest `
  tests\rei\test_gui.py `
  tests\rei\test_gui_semantic_lab.py `
  -q --basetemp output\pytest-c8-doc-gui-final-v2
# 46 passed in 10.82s

app\backend\.venv\Scripts\python.exe -m pytest `
  tests\rei\test_gui.py `
  tests\rei\test_gui_semantic_lab.py `
  tests\rei\test_persistence.py `
  -q --basetemp output\pytest-c8-doc-focused-final-v3
# 119 passed in 12.07s

app\backend\.venv\Scripts\python.exe -m pytest `
  tests\rei\test_gui.py `
  tests\rei\test_gui_semantic_lab.py `
  tests\rei\test_persistence.py `
  tests\rei\test_engine.py `
  -q --basetemp output\pytest-c8-security-final-partition
# 138 passed

app\backend\.venv\Scripts\python.exe -m compileall -q `
  app\backend\rei\persistence\artifacts.py app\gui `
  tests\rei\test_gui.py tests\rei\test_gui_semantic_lab.py `
  tests\rei\test_persistence.py
# PASS

node --check app/gui/static/app.js
# PASS

git diff --check -- app/backend/rei/persistence/artifacts.py app/gui `
  tests/rei/test_gui.py tests/rei/test_gui_semantic_lab.py `
  tests/rei/test_persistence.py `
  plans/REI_next_phases_merge_semantic_architecture_2026-07-14.md
# PASS

app\backend\.venv\Scripts\python.exe -m pytest tests\rei -q `
  --basetemp output\pytest-c8-doc-full-final-v4
# 1002 passed in 325.55s
```

The 119-test count includes the 46 GUI/API tests; the 138-test count includes
both. These overlapping results must not be added together. The final full
count includes all focused tests and must likewise not be summed with them.
The full suite and final two-cycle browser evidence were recorded immediately
before the phase commit.

Browser QA uses a real local Uvicorn process and Microsoft Edge through
Playwright in a fresh `c8releasefinal` session. The result is **GREEN**:

- all six workbench tabs rendered and remained navigable;
- initial load created no cycle;
- the request ledger contained exactly one successful `debug=false` cycle POST
  and one successful `debug=true` cycle POST;
- normal Racio and the whole Ego timeline were structurally redacted;
- debug Racio and Ego exposed the evaluator comparison, and disabling the
  toggle removed it immediately without another POST;
- Emocio explicitly reported no valuation and no embeddings where those stages
  had not run; Instinkt rendered every required process section;
- Ego showed two ordered events, and the persisted final-v5 trace contained two
  measures under the same Ego identity;
- the mobile viewport measured `390/390` pixels with no horizontal overflow;
- the final console contained 0 errors and 0 warnings.

The desktop and mobile screenshots were visually inspected. Evidence is stored
below ignored `output/` paths and is not part of the source commit.

## Model runs and semantic authority

- Model-backed runs: **0**.
- Image generation/edit runs: **0**.
- Ollama calls: **0**.
- New canon claims: **0**.
- New implementation hypotheses: **0**.
- New open questions: **0**.

The GUI displays checked-in evidence and deterministic runtime fixtures. It
does not convert a placeholder image slot, embedding lineage, manual body
fixture or historical model record into new empirical evidence.

## Artifacts

Checked in:

- this acceptance report;
- the C8 source, tests and plan status described above.

Generated for local verification and intentionally ignored:

- visually inspected `desktop-ego.png` and `mobile-ego.png` screenshots under
  `output/playwright/c8-gui-2026-07-15/` (plus earlier Semantic/Racio captures);
- the final two-measure browser trace under
  `output/c8-browser-qa-final-v5/ego-traces/`;
- local C8 browser-run Ego traces and runtime logs under `output/` and `tmp/`;
- isolated pytest temporary directories under `output/`.

## Known limitations

- Semantic Lab is a review projection, not an authoring or reviewer-write UI.
- 180 of 192 semantic variants have no execution evidence and remain explicitly
  `not_executed`; the GUI does not manufacture an actual route.
- Emocio image slots and embedding provenance expose the current checked-in
  boundary; C8 does not execute a live image generator, editor, encoder or VLM.
- The displayed Instinkt predicted effects come from bounded deterministic or
  explicitly marked manual-fixture evidence, not a newly validated model.
- The concurrency gates are process-local and are not a distributed scheduler.
- The supported workbench deployment uses one server process. Partition
  capacity checks are not a cross-process reservation protocol; a multi-process
  deployment requires external coordination and is not supported by C8.
- Explicit remote/debug opt-ins are unauthenticated trusted-single-user modes;
  they enlarge the exposure boundary, and neither `ego_id` nor its partition
  digest authorizes access.
  An untrusted or multi-user deployment requires external authentication and
  authorization and is not supported by this workbench.
- Restart recovery deliberately enumerates at most 64 entries inside one
  SHA-256-derived Ego run partition and retains at most 30 measures per GUI Ego
  session. A larger partition or session fails closed and requires a new or
  bespoke recovery workflow rather than an unbounded scan.
- Native bundles above 2 MiB are rejected before GUI persistence. This is a
  workbench recovery bound, not a general REI architecture limit.
- C7 research quality remains blocked; C8 grants no semantic or production
  authority and does not make C9 ready.

## Regression risk and rollback

Regression risk is moderate because the phase changes the persistence read
surface, server boundary, cycle view contract and most browser rendering, but
it is bounded by strict
request validation, structural redaction tests, frozen artifact checks,
focused/full automated suites and real-browser QA. The change does not alter a
native processor, Character governance, EgoTrace schema or append-only
contract, provider selection or model registry.

Rollback is `git revert <C8 phase commit>`. No migration, generated dataset,
external write or model registry change must be undone separately.

## Required phase report

```text
Phase: C8 — GUI semantičnega laboratorija
Branch: main
Base main SHA: 1d8c391bb8e60f02e0f7552463069c257699b9fc
Head SHA: phase commit containing this report; a self-referential SHA is intentionally not embedded
Changed files: app/backend/rei/persistence/artifacts.py, app/gui/README.md, app/gui/__init__.py, app/gui/server.py, app/gui/static/app.js, app/gui/static/index.html, app/gui/static/styles.css, app/gui/view_model.py, tests/rei/test_gui.py, tests/rei/test_persistence.py, and the phase plan
New files: app/gui/semantic_lab.py, app/gui/storage.py, tests/rei/test_gui_semantic_lab.py, and this acceptance report
Deleted files: 0
Architecture changes: integrity-checked read-only Semantic Lab projection; structurally redacted Racio and whole-Ego views; modality-specific workbench projections; Ego-partitioned bounded verified restart recovery; longitudinal Ego UI
Runtime changes: read-only semantic endpoint; explicit cycle execution; SHA-256 ego_id run partitions; at most 64 partition entries/30 measures; 2 MiB pre-persistence native-bundle cap; read-only Ego-scoped verified image route; loopback/host/origin/content-type boundary; process-local single-flight gates; restrictive response headers
Canon claims added: 0
Implementation hypotheses added: 0
Open questions added: 0
Tests run: focused GUI/API pytest; full tests/rei pytest; compileall; Node syntax; git diff check; real-browser desktop/mobile QA
Tests passed: 1002 tests/rei full; 138 expanded focused including 119 GUI/Semantic/persistence and 46 GUI/API; real-browser desktop/mobile QA green
Tests failed: 0
Model-backed runs: 0
Artifacts created: C8 source/tests/report; ignored browser screenshots, Ego traces, logs and pytest temporary files
Known limitations: read-only review UI; 180 variants not executed; no live visual/model arm; single-process/process-local coordination; 64-entry/30-measure/2-MiB workbench recovery bounds; remote opt-in unauthenticated/trusted-single-user only; C7 research gate still blocked
Regression risk: moderate and concentrated in persistence/GUI/server read surfaces; no native processor, governance, provider or registry change
Rollback path: git revert <C8 phase commit>
Proposed commit: feat(gui): add semantic native-process and longitudinal Ego workbench
Recommended next phase: controlled image/model remediation for the open C3/C4/C7 research blockers; C9 remains premature
```
