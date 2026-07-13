# REI Native Composition Architecture — B14 Acceptance Record

Status: **accepted for the active runtime, with the limitations below**

Acceptance date: 2026-07-13

Canonical terminology: Slovenian

Implementation head tested by the final model-backed run:
`23af9b06602e097d6f7ea7ceb14a8bbbfbc08079`

Final report commit: resolve the commit with subject
`docs: record native REI architecture acceptance and rollback path` by running
`git log -1 --format=%H -- Docs/evals/rei_native_architecture_acceptance_2026-07-13.md`.

## 1. Acceptance decision and scope

The native-modality architecture defined in
`plans/REI_native_composition_architecture_upgrade_2026-07-13.md` satisfies the
B14 deliverables and the final Definition of Done. The archived textual
three-LLM baseline is not an active runtime. The active system separates native
Racio, Emocio and Instinkt processing; deterministic ordinal governance;
Racio-mediated conscious commitment; behavior; and append-only Ego composition.

This acceptance is a software-architecture decision. It is not empirical
validation of REI theory, a psychological or medical claim, a characterization
of a real person, or final model selection. The Granite integration below is one
tested Racio provider path, not the chosen production base model.

## 2. Verified technology and model baseline

Current upstream information was checked before the live run.

| Component | Accepted/tested version | Upstream basis |
| --- | --- | --- |
| Ollama | `0.31.2` stable | [Ollama v0.31.2 release](https://github.com/ollama/ollama/releases/tag/v0.31.2); the available `0.32.0-rc0` was not treated as stable |
| Ollama Generate API | v0.31.2 request contract | [Generate API](https://docs.ollama.com/api/generate) and [v0.31.2 `GenerateRequest`](https://github.com/ollama/ollama/blob/v0.31.2/api/types.go) |
| Granite | `granite4.1:30b`, `Q4_K_M`, full digest `3f3e5df8a021439fd6f867a0e526bdc303cac79c811201cb6bac193298cb9fcd` | [Ollama Granite 4.1 tags](https://ollama.com/library/granite4.1/tags) and [IBM Granite 4.1 30B model card](https://huggingface.co/ibm-granite/granite-4.1-30b) |
| Python / pytest | Python `3.11.15`; pytest `9.1.1` | Versions observed in the repository virtual environment |
| GUI backend | FastAPI `0.139.0`; Uvicorn `0.51.0`; Pydantic `2.13.4` | Versions observed in the repository virtual environment |
| Browser smoke | Playwright CLI `0.1.17`; Microsoft Edge `150.0.4078.65` | npm `latest` was `0.1.17`; [Edge 150 release notes](https://learn.microsoft.com/en-us/microsoft-edge/web-platform/release-notes/150) |

## 3. Archive integrity and rollback anchor

The immutable baseline is stored in
`archive/rei_v3_text_llm_baseline_2026-07-13/`.

- `SOURCE_COMMIT` records
  `05996b2b4a34cf6dd654e032d5dbc26bb5373ef0`.
- `FILES.sha256` contains 75 payload entries.
- `MANIFEST.json`, `BASELINE_VERIFICATION.md`, the snapshot, the reproducible
  archive script and rollback instructions are present.
- `tests/test_archive_integrity.py` validates the complete inventory and
  `tests/test_archive_boundary.py` validates active/archive isolation.
- Annotated tag `rei-v3-text-llm-baseline-2026-07-13` has tag-object SHA
  `ea04d0ef0da3bd3d6036eefbe552731a2083461e` and dereferences to
  `05996b2b4a34cf6dd654e032d5dbc26bb5373ef0`.
- `git ls-remote --tags origin` returned the same tag object and dereferenced
  commit for the remote tag.

## 4. Final automated test evidence

All final commands ran after the Ollama provider and its live-integration fixes
were committed.

| Scope | Command | Result |
| --- | --- | --- |
| Controlled architecture suite | `python -m pytest tests/rei tests/test_archive_boundary.py tests/test_archive_integrity.py tests/test_native_cutover.py -q --basetemp output/pytest-b14-final-core-mrjmo49a` | **632 passed**, 0 failed, 29.43 s |
| Literal discoverable working-tree suite | `python -m pytest -q --basetemp output/pytest-b14-final-full-mrjmoulc` | **643 passed**, 0 failed, 29.38 s |
| Ollama/provider adversarial suite | `python -m pytest tests/rei/test_ollama_provider.py -q` | **19 passed**, including malformed output, remote/redirect, digest drift, thinking, length termination, and exact GPU-residency rejection |
| Provider/engine/protocol regression slice | provider + deterministic provider + protocol + engine tests | **57 passed**, 0 failed |

The literal suite included the user-owned, untracked `tests/v2/` tests. The
controlled suite is the acceptance denominator for the committed architecture;
the larger literal suite demonstrates that all tests discoverable in the dirty
working tree also passed. Pre-existing user-owned working-tree files were not
included in architecture commits.

### 4.1 Real browser smoke

The active loopback GUI was exercised with Playwright CLI against Microsoft
Edge, not only through an HTTP test client.

- viewport `1440 × 1000`: deterministic cycle completed, all invariants passed,
  and Native, Communication, Character and Ego tabs rendered;
- viewport `390 × 844`: the debug Communication view rendered without
  horizontal overflow;
- browser console: 0 errors and 0 warnings;
- measured document width equaled viewport width at both sizes;
- the Character view showed separate mandate, conscious-decision and behavior
  records;
- the Ego view showed the measure/trace, composition snapshot, self-narrative
  and three modality-specific projections;
- the loopback-only evaluator debug switch exposed clearly labelled native
  ground truth and stated that Racio had not received it;
- disabled image rendering produced explicit structured-scene wells and did
  not invent pixels or contact an image model.

Local screenshots are under `output/playwright/b14-final/`; `output/` is
intentionally not a committed source tree.

## 5. Deterministic native-cycle evidence

The model-free runner was executed in a fresh create-only store:

```powershell
app\backend\.venv\Scripts\python.exe scripts\run_rei_native_cycle.py `
  --runs-root output\evals\b14-deterministic-final-20260713a\runs `
  --ego-traces-root output\evals\b14-deterministic-final-20260713a\ego-traces
```

Result:

- run ID: `b11-e2e-run`;
- stored artifacts: 45;
- model flags for native R/E/I: `false,false,false`;
- all runtime invariants passed;
- cold `FileArtifactStore.verify_run(...)` passed from a new store object;
- run-manifest file SHA-256 (the runner summary's `manifest_hash` field):
  `dab3415658e19730954f49a96003dc6cdb5a5282dd22e9336730157db4a330fc`;
- embedded canonical `RunManifest.manifest_hash`:
  `29c4cb263f25c14015d0a48334641f2a57585c29c1948c596bad5083bf499fc9`;
- invariant report hash:
  `2ae84f3aa52b8696e940019e710625642528f52a1b1fd4d8abcbbf7b9fc35354`;
- immutable native-bundle hash:
  `0c0aad5d23463ded33f25ac9e0d8df161adcc53994ffb1c53d9db24472f37189`.

## 6. Canonical 12 × 13 fixture matrix

`scripts/run_rei_native_profile_matrix.py` evaluated the 12 checked-in frozen
native bundles across all 13 structural character profiles.

- fixtures: 12;
- profiles: 13;
- rows: **156**;
- native processor executions: **0**;
- matrix ID: `profile_matrix_e7a58ae9d6b89a69959e89331b763a4d`;
- canonical matrix hash:
  `b7249e1d4b4f7aeccdbb48718c1aaaf96e6ea49ed0d8f64b598ed7781974ee31`;
- output-file SHA-256:
  `3592e93b75f80de91aa4b7e251b27a91e35807b509060ac6e07b24265bf213b5`;
- coverage: 156 B10 oracle rows, 36 pair-conflict rows, 9 thirteenth
  majority rows, 13 `simulated_spoznanje` rows, 54 mandate/conscious-option
  divergence rows, and 130 conscious/behavior-state divergence rows.

For each fixture, its unchanged frozen bundle ID/hash is reused across all 13
profiles; character does not rerun or influence native processors.

## 7. Controlled Granite 4.1 full-GPU Racio smoke

Only Racio crossed the model boundary. Emocio and Instinkt used the same
deterministic native processors as the model-free run. Governance,
interpretation of E/I manifestation, conscious commitment, behavior and Ego
composition remained deterministic downstream code.

Canonical command:

```powershell
$env:REI_OLLAMA_NUM_CTX = "65536"
$env:REI_OLLAMA_NUM_GPU = "999"
app\backend\.venv\Scripts\python.exe scripts\run_rei_native_ollama_smoke.py `
  --model granite4.1:30b `
  --expected-model-digest 3f3e5df8a021439fd6f867a0e526bdc303cac79c811201cb6bac193298cb9fcd `
  --num-ctx 65536 --num-gpu 999 --require-full-gpu `
  --run-id b14-ollama-racio-smoke-20260713c `
  --ego-id b14-ollama-racio-smoke-ego-20260713c `
  --runs-root output\evals\b14-ollama-racio-smoke-20260713c\runs `
  --ego-traces-root output\evals\b14-ollama-racio-smoke-20260713c\ego-traces `
  --summary-output output\evals\b14-ollama-racio-smoke-20260713c\summary.json `
  --timeout-seconds 600 --keep-alive 10m
```

### 7.1 Provenance and placement

- source commit:
  `23af9b06602e097d6f7ea7ceb14a8bbbfbc08079`;
- Ollama server: `0.31.2`;
- model: `granite4.1:30b`, `Q4_K_M`, model context 131072;
- approved and observed digest:
  `3f3e5df8a021439fd6f867a0e526bdc303cac79c811201cb6bac193298cb9fcd`;
- call: seed `314159`, temperature `0.0`, `num_ctx=65536`,
  `num_gpu=999`, `num_predict=1536`, `think=false`, `raw=false`,
  `logprobs=false`, `truncate=false`, `shift=false`, `stream=false`, no
  fallback;
- `/api/ps`: `size=26982660177`, `size_vram=26982660177`, context `65536`;
- `wsl ollama ps`: `100% GPU`, context `65536`;
- `nvidia-smi` after completion while loaded: 26407 MiB used of 32607 MiB;
- after the evidence capture, `ollama stop granite4.1:30b` returned the server
  to an empty process list and GPU usage to 73 MiB.

Exact full residency is accepted only when `size_vram == size`; a rounded 100%
display is insufficient. Metadata with `size_vram > size` is rejected.

### 7.2 Result integrity

- model-backed minds: exactly `["R"]`;
- stored artifacts: 46;
- run status: completed;
- all 11 runtime invariants passed;
- cold manifest verification passed;
- run-manifest file SHA-256 (the runner summary's `manifest_hash` field):
  `a954e18baeead9b2160289541cd449fb9859b02b83e6cfb306b957b590e2c01a`;
- embedded canonical `RunManifest.manifest_hash`:
  `5d01c74fd712566480902105872d92005dce3f62ebae5780728fe61d5158a3a4`;
- invariant report hash:
  `5185fb14d6f2819a653dd2353128cff997af15c4cb6a528b25418612bb7ce272`;
- response-evidence ID:
  `ollama_racio_response_f1eb827ec0de3cd76f4bb6760da044d7`;
- response-evidence hash:
  `523d88a0fbaa0a521a512b613b4209f906860afe6286dd6c9b8b925d12c7f11b`;
- response-envelope hash:
  `ff33239ec90dcc193e83ea2ee0992da4d8d42335bad0953e6d9d576a76d1dcb4`;
- completion: `done_reason=stop`, 606 prompt tokens and 205 evaluated
  output tokens;
- chosen option: `option_restore`;
- immutable native-bundle hash:
  `347fce097a7c228ffb13683892c78202a3a1a0a1e7382d885f70ee095b8cb16c`.

The persisted evidence closes packet hash, call-spec hash, provider/model
identity, request-payload hash, selected response metadata, active placement,
structured output, conclusion lineage and provider call outputs. It is written
before the manifest and is included in cold run verification.

### 7.3 Fail-closed integration observations

Two non-accepted attempts preceded the accepted `c` run:

1. attempt `a` was terminated when an independent audit found that rounded GPU
   percentage was too permissive; no manifest or result artifact was committed;
2. attempt `b` was rejected because the model copied one value across distinct
   fact/unknown/causal roles; strict Pydantic validation rejected it and no
   manifest was committed.

The provider was then changed to require exact GPU byte equality and the Racio
instruction was clarified to preserve disjoint semantic roles. Both changes
were committed before attempt `c`; the accepted manifest therefore names the
exact corrected source SHA. There was no hidden retry, fallback provider or
unrecorded successful run.

## 8. Runtime architecture invariants

The accepted live run passed these content-addressed checks:

1. `native_bundle_frozen`;
2. `structural_character_preserved`;
3. `governance_bound_to_bundle`;
4. `conscious_decision_is_racio`;
5. `behavior_bound_to_decision`;
6. `narration_is_downstream`;
7. `ego_measure_closes_cycle`;
8. `ego_trace_append_only_result`;
9. `snapshot_cites_trace`;
10. `manifest_complete`;
11. `native_provider_outputs_are_conclusions_only` (provider output never
    claims deterministic bundle assembly).

These runtime checks are necessary but not the sole acceptance proof. The
canonical fixture matrix, domain tests, communication tests, browser smoke and
archive/cutover guards provide the broader Definition-of-Done evidence.

## 9. Final Definition of Done audit

| # | Required property | Acceptance evidence | Result |
| --- | --- | --- | --- |
| 1 | Old architecture archived, tagged and hash-manifested | 75-entry archive inventory; annotated local/remote tag; archive tests | Pass |
| 2 | Rollback path documented | Section 14 and archive `README.md` | Pass |
| 3 | Active code does not import archive | `test_archive_boundary.py` and AST cutover guards | Pass |
| 4 | Native processors are modally separate | profile-blind domain/provider contracts and engine tests | Pass |
| 5 | Racio is linguistic-symbolic | Racio packet/conclusion tests and grounded Ollama structured-output path | Pass |
| 6 | Emocio builds and evaluates scenes before Racio interpretation | Emocio visual-state/valuation tests and engine ordering | Pass |
| 7 | Instinkt builds body rollouts/protective conclusion before verbalization | Instinkt trajectory, association and manifestation tests | Pass |
| 8 | Same frozen bundle runs through all 13 characters | 12 × 13 matrix with 0 native executions | Pass |
| 9 | Character is ordinal and stable | exact 13-profile contract tests | Pass |
| 10 | State/intensity does not alter character | confidence/intensity and functional-override tests | Pass |
| 11 | Pair conflict has no artificial tie-breaker | subordinate/Racio/LLM tie-break guards and pair tests | Pass |
| 12 | Thirteenth profile uses 2-of-3 | nine majority rows and explicit rule tests | Pass |
| 13 | `simulated_spoznanje` requires all three | 13 convergence rows and profile-independent tests | Pass |
| 14 | Conscious decision is always Racio's | B10 decision type tests and runtime invariant | Pass |
| 15 | Mandate, conscious decision and behavior are separate | distinct typed IDs/lineage, tests and GUI view | Pass |
| 16 | Translation gap is explicit and measurable | communication fidelity/gap/tamper tests and GUI boundary | Pass |
| 17 | Acceptance does not imply agreement | acceptance/behavior divergence tests | Pass |
| 18 | Ego has no voice or vote API | forbidden-field tests and ADR-004 | Pass |
| 19 | `EgoMeasure` is one takt | measure lineage tests and runtime invariant | Pass |
| 20 | `EgoTrace` is executed history | append-only memory/file stores and correction tests | Pass |
| 21 | Snapshot recognizes sourced motifs/tensions | content-addressed snapshot and source-claim tests | Pass |
| 22 | History returns in three modalities | deterministic R/E/I projection tests and GUI | Pass |
| 23 | GUI distinguishes native signal, manifestation and Racio interpretation | test suite plus desktop/mobile Edge smoke | Pass |
| 24 | All canonical fixtures and invariants pass | 632 controlled tests, 643 literal tests, fresh cycle and 156-row matrix | Pass |
| 25 | QLoRA is not part of implementation | active runtime scan has no QLoRA/training entrypoint; cutover guard | Pass |

## 10. Known limitations

- This is a conceptual simulator, not an empirically validated model of a real
  person and not suitable for diagnosis.
- Only one controlled Granite Racio run is acceptance evidence; it is not a
  quality benchmark, statistical evaluation or final-model decision.
- The IBM model card's supported-language list does not include Slovenian. The
  accepted model smoke used the checked-in English fixture; Slovenian model
  quality has not been validated.
- A fixed seed and exact parameters improve provenance but do not guarantee
  bit-identical inference across Ollama/runtime/hardware revisions.
- The response evidence persists the canonical full-envelope hash and selected
  response fields, not the complete raw response envelope; a cold audit cannot
  independently recompute that envelope hash without the original response.
- Source cleanliness and `HEAD` are checked immediately before generation;
  there is no second source-tree check after the completed run, leaving a small
  concurrent-drift window in uncontrolled environments.
- Generate timeout and metadata endpoint timeouts are individually bounded,
  not one shared end-to-end deadline.
- The repository has explicit typed protocols, frozen Pydantic contracts and
  strict runtime validation, but no repository-wide mypy/pyright configuration;
  this report does not claim a whole-tree static type-check pass.
- The user-owned dirty working-tree overlays and untracked canon-v2 experiments
  were preserved and excluded from B14 commits.

## 11. Model integrations still missing or intentionally untested

- a real Emocio raster renderer or text-to-image provider;
- a VLM interpreter, image encoder or learned visual-world model;
- learned Instinkt/body-dynamics or interoceptive models;
- model-backed manifestation interpreter, conscious committer, narrator or Ego
  reflector;
- Slovenian-language model evaluation;
- multi-model comparison, robustness, latency and quality evaluation.

Structured Emocio scenes remain authoritative when rendering is disabled.
Generated images cannot add grounded evidence. No image was generated during
B14. QLoRA, LoRA, SFT, training-data generation and final base-model selection
remain outside this upgrade.

## 12. Open questions

The normative uncertainty register remains
`knowledge/canon_v2/open_questions.md`. Open areas include:

- empirical calibration of confidence, intensity, acceptance and translation
  fidelity;
- evidence for genuinely independent processor routes without exposing hidden
  chain of thought;
- Emocio visual valuation, renderer boundaries and real image-model choice;
- virtual-body dynamics, Instinkt calibration and learned alternatives;
- pair-conflict handling, functional availability and conclusion identity;
- Ego composition semantics, projection quality and final `PersonState` scope;
- Slovenian model quality, safety boundaries, Življenje/metaphysical limits and
  legacy-weight display.

An open question is not runtime truth and must not be silently filled by a
provider heuristic.

## 13. Architecture-upgrade commit ledger

1. `2286f68bd2b1250041ed44f738745fe5316105df` — `chore(archive): freeze textual REI-v3 architecture before native-modalities rewrite`
2. `d1a19b9f1d4b9c1cf709342aa883c2b2d45491c5` — `docs(architecture): define native REI processors and Ego composition`
3. `668dc42edd1259b8ba7277287ad21868dcd4bc97` — `feat(core): add REI native domain model and provider protocols`
4. `1d887996706c3d7b743ff59480beb21f69d1be50` — `feat(governance): implement ordinal character authority and causal fixture matrix`
5. `ff4309af09c4438b961ca2648e1e56c65d82a8cc` — `feat(ego): model Ego as append-only composition across REI cycles`
6. `ecc51ada25919228e3ef9a8bfe813670d47f7948` — `feat(racio): add independent verbal-analytical native processor`
7. `88cbc84c73f86d065fd7649d4778c14475913a71` — `feat(emocio): add visual scene world model and native policy`
8. `7953dde443cd74eb5d95bcea7fb8937cc1c79ffe` — `feat(emocio): integrate optional local visual rendering artifacts`
9. `16c1fd1e73c0d6d38b6bdabca432eeda822ddfe9` — `feat(instinkt): add embodied protective simulator and associative memory`
10. `ff59d0183c9e0ccdcdd0b6f7e9c543bd6e2aff89` — `feat(communication): model Racio translation of Emocio and Instinkt`
11. `2a5eb514340694e4c8cd37f67421dda0f3d554a0` — `feat(conscious): separate Racio decision, governance mandate and behavior`
12. `7ecd4f9869fb4db275cf7a849b5c4f0292f7237e` — `feat(engine): orchestrate native REI cycle and Ego composition`
13. `22c6755445d615019192aaba212cf2bc4525f24e` — `feat(gui): add multimodal REI composition workbench`
14. `8ce2a3a65cdd995dbfc10a4d915d1ae38d414426` — `refactor!: promote native-modalities REI architecture to active runtime`
15. `9722b6ba970676e8c5e62db20eab5a670bed08db` — `fix(runtime): harden native GUI and model shutdown`
16. `1592dfa79ff5b1d8db26a0fb77cde79591dfe9e8` — `feat(provider): add native Ollama Racio smoke path`
17. `141c361b0e2db020a3870bdd73097b7f358fac2d` — `fix(provider): require exact Ollama GPU residency`
18. `23af9b06602e097d6f7ea7ceb14a8bbbfbc08079` — `fix(provider): clarify grounded Racio output roles`
19. Final B14 report commit — `docs: record native REI architecture acceptance and rollback path`; resolve its non-self-referential SHA with the command at the top of this report.

## 14. Safe rollback to the archived baseline

Rollback must create a separate worktree; it must not reset or overwrite the
active branch or dirty working tree.

```powershell
git fetch origin --tags
git worktree add -b rollback/rei-v3-text-llm-baseline-2026-07-13 `
  ..\rei-v3-text-baseline `
  rei-v3-text-llm-baseline-2026-07-13
git -C ..\rei-v3-text-baseline rev-parse HEAD
```

Expected result:

```text
05996b2b4a34cf6dd654e032d5dbc26bb5373ef0
```

If the example branch or directory already exists, choose a new branch name and
empty sibling directory. Do not use `git reset --hard`, forced checkout or a
force-push as a rollback procedure.

## 15. Final acceptance statement

B14 is complete when this report's exact commit is present on the active remote
branch and the requirement-by-requirement audit still matches the committed
tree. All required architecture gates passed on 2026-07-13. Remaining items in
Sections 10–12 are explicit limitations or future work, not hidden completion
claims.
