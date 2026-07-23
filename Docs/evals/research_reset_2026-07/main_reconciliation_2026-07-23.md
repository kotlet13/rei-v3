# MAIN-R1 — main repository and research reconciliation

Date: 2026-07-23

Audit branch: `codex/main-reconciliation-audit`

Audited main: `8eddb2de68852aab4d4e7d29df090f81f5e73002`

Compared branches:

- `codex/racio-gemma4-shadow-gui` at
  `f3408e71f474a440bdbafc9fbc5c66ec3ebfd446`;
- `codex/rei-english-runtime-smoke` at
  `fb449ed523669202f2bd3dc216452ce327b7874e`.

## Scope and method

This document is the only repository artifact created by MAIN-R1. The audit
made zero model calls, changed no runtime semantics, added no evaluation
infrastructure, and performed no merge, cherry-pick, rebase, or squash.

The comparison used commit-graph inspection (`merge-base`, symmetric
`rev-list`, and ancestry checks), tree comparison (`ls-tree`), direct diffs,
and non-mutating synthetic merges (`merge-tree --write-tree`). “Branch-only”
below means that the path exists in the branch tree and does not exist in the
audited main tree. It does not mean that every path modified by a branch is
listed as branch-only.

Both branches have the same merge base:

`bc8c83d1534a2aad9f5f41d2a69c6bafb9ac7239`

The shadow-GUI head is an ancestor of the English-runtime-smoke head. Merging
the English branch would therefore preserve the shadow-GUI execution commit
without a separate merge of the shadow-GUI branch.

## Main-only commits shared by both comparisons

Each compared branch lacks the following ten commits that are present on
audited main:

1. `8eddb2de68852aab4d4e7d29df090f81f5e73002` — Merge pull request #6
   from `codex/c4-stage1-review-integration`.
2. `520722e85554478d756e1fccd8ebdd98e67bc82e` — `test(eval): reflect
   pre-containment POSIX refusal`.
3. `a26dc4f03ea78695b05fda8d698e5b6cc267e137` — `fix(eval): make C4
   process-tree test platform aware`.
4. `090b22f3fb6ff281078339672b949ad6e027527a` — `fix(eval): close C4 IPC
   readers and document trust boundary`.
5. `f328cbe3cf99430a3fbabde0f433ae5c81ecb7a6` — `feat(eval): add C4
   Stage 1 review runtime`.
6. `de4eef296b4b9efbd2db5c4808d1ccdfbccfe680` — Merge pull request #5
   from `codex/research-reset-docs-integration`.
7. `453e4fd6529760c8a43e57f886e6dae45fe20413` — `docs(research): close
   superseded plans and qualify v2 evidence`.
8. `782edf3b90a8160543c61fd8d5275767b20265ce` — `docs(plan): normalize
   preserved plan formatting`.
9. `49c945aa2ebbe651fc5e1245c74335e03ec98ffd` — `docs(research):
   preserve canonical v2 and C5 artifacts`.
10. `444a072cf9cebee8b0699570debad4ca5fbdc240` — `docs(plan): defer image
    review to Gemma vision phase`.

There are no patch-equivalent commits across either symmetric difference.
PR #5 and PR #6 are therefore real main-side history, not merely renamed
copies of commits on the two compared branches.

## Branch 1 — `codex/racio-gemma4-shadow-gui`

### Commit topology

- merge base:
  `bc8c83d1534a2aad9f5f41d2a69c6bafb9ac7239`;
- commits main lacks: one;
- commits the branch lacks: the ten main-only commits listed above.

The sole branch-only commit is:

- `f3408e71f474a440bdbafc9fbc5c66ec3ebfd446` — `feat(gui): visualize
  verified Gemma text-shadow evidence`.

### Branch-only source and evidence

Active source that exists only on the branch:

- `app/gui/shadow_view.py`.

The only branch-only supporting test is:

- `tests/rei/test_gui_shadow_view.py`.

Evidence that exists only on the branch:

- `Docs/evals/research_reset_2026-07/gemma4_shadow_gui_s2a.md`.

The commit also modifies `app/gui/server.py`, `app/gui/static/app.js`,
`app/gui/static/styles.css`, and `tests/rei/test_gui.py`. A synthetic merge
against current main contains seven changed paths, 2,383 insertions, and six
deletions.

### Expected conflicts and post-PR relevance

`git merge-tree --write-tree` completed without a textual conflict and
produced synthetic tree
`42f57520c585f7b6b87c25b1ca1d9a607f57a0ea`. PR #5 restores documentation,
historical canon material, plans, and their validators; PR #6 adds inactive
C4 review infrastructure. Neither overlaps the S2A patch sufficiently to
cause a textual conflict.

The S2A security and authority boundaries remain meaningful after PR #5 and
PR #6: loopback-only GET replay, allowlisted evidence IDs, cold verification,
no provider import, no model call, no evidence write, and no authority. The
branch as an integration unit is nevertheless superseded because its only
commit is already an ancestor of the later English branch, whose GUI evolved
the replay schema and selector. Merging this branch separately would add
history and integration work without preserving any identity that the later
branch does not already preserve.

**Branch recommendation: `abandon as superseded`.** Do not merge this branch
separately. Port the still-valid S2A presentation and safety contract from the
later branch as part of one reviewed integration.

## Branch 2 — `codex/rei-english-runtime-smoke`

### Commit topology

- merge base:
  `bc8c83d1534a2aad9f5f41d2a69c6bafb9ac7239`;
- commits main lacks: 22;
- commits the branch lacks: the ten main-only commits listed above.

The 22 branch-only commits, in execution order, are:

1. `f3408e71f474a440bdbafc9fbc5c66ec3ebfd446` — `feat(gui): visualize
   verified Gemma text-shadow evidence`.
2. `e607993baafa2ebe743251d3baaee38e2e9c190d` — `feat(runtime): enforce
   English-only local model boundaries`.
3. `55862e91bf0c91dd98387ddd71a962e61f0ab6fc` — `test(shadow): prepare
   sealed English runtime smoke`.
4. `3979b7884eb9b5196d47bc4ad188f4dfab60cad2` — `docs(shadow): seal
   English runtime Gemma cycle`.
5. `2d2ddd20d2b3f60a2e50c4301312c7bb1b5d97f0` — `docs(shadow): preserve
   successful English smoke evidence`.
6. `4314767a7c0770dbc9b42c58b61106d2b492ac1b` — `fix(shadow): use valid
   manifest ID for English smoke evidence`.
7. `9a825cdb3571c573fdeb3a14fe1e55b016957f4a` — `docs(shadow): close
   English runtime smoke evidence`.
8. `da4e91ecfe8a57c30f590a614cf8446d42d8981d` — `fix(shadow): preserve
   English smoke bytes across checkouts`.
9. `9fdda7cb28afebe62d0089f0b6969ba52d04a391` — `fix(gui): make verified
   English runtime evidence the default shadow view`.
10. `1f118c0d64cfb1ac02357dcf1a299d2c16041041` — `feat(shadow): explain
    abstention and expose exact model input`.
11. `700fed8faa3619af0247496b9e0fac87d0cafb7d` — `docs(shadow): bind
    explained smoke to implementation`.
12. `a385158c852c0ab30ab837880c660ee7dd5fad15` — `docs(shadow): seal
    explained English shadow cycle`.
13. `bfeaaa4203d6457ff87bf83527e87962a48c19aa` — `docs(shadow): preserve
    explained English model evidence`.
14. `f817509e932c671696597930f17c93034d73b569` — `fix(gui): explain
    shadow results and expose exact inputs`.
15. `8e1a83309c31f138e8c24aa6624fcd8e1553285a` — `fix(evidence): preserve
    EN2 byte stability across checkouts`.
16. `5c2874a04cf5a9630f75faed4e279933216aba64` — `fix(gui): expose shadow
    calls and validation outcomes`.
17. `97c9f499e81422769d67760e23390c5fd83f6301` — `fix(shadow): preserve
    rejected Gemma validation evidence`.
18. `acbcab3c15dedddc85a9d841cd6406436db7b560` — `docs(shadow): configure
    observable Gemma cycle`.
19. `a6a6a9319595bb210c96d8e1934edfd68ddcf1e6` — `docs(shadow): seal
    observable Gemma validation cycle`.
20. `5edc3cb270fda1ded8e2b5ac9e5356c80e19c498` — `docs(shadow): preserve
    observable EN3 model evidence`.
21. `d075b4066daeababb6860438448a824856cd4bfc` — `fix(gui): expose
    observable EN3 shadow evidence`.
22. `fb449ed523669202f2bd3dc216452ce327b7874e` — `fix(evidence): preserve
    EN3 byte stability across checkouts`.

### Branch-only active source

The branch has 11 source or executable-script paths that do not exist on main:

- `app/backend/rei/communication/epistemic_interpreter_en.py`;
- `app/backend/rei/communication/epistemic_interpreter_en_explained.py`;
- `app/backend/rei/providers/language_policy.py`;
- `app/backend/rei/providers/ollama_en.py`;
- `app/backend/rei/providers/ollama_gemma4_epistemic_en.py`;
- `app/backend/rei/providers/ollama_gemma4_epistemic_en_explained.py`;
- `app/backend/rei/providers/ollama_interpreter_en.py`;
- `app/gui/shadow_view.py`;
- `scripts/run_gemma4_racio_english_shadow_smoke.py`;
- `scripts/run_gemma4_racio_explained_shadow_smoke.py`;
- `scripts/run_gemma4_racio_observable_shadow_smoke.py`.

The branch also has seven branch-only test paths:

- `tests/evaluation/test_gemma4_epistemic_en_provider.py`;
- `tests/rei/test_english_explained_shadow_smoke.py`;
- `tests/rei/test_english_observable_shadow_smoke.py`;
- `tests/rei/test_english_runtime_shadow_smoke.py`;
- `tests/rei/test_epistemic_interpreter_en.py`;
- `tests/rei/test_gui_shadow_view.py`;
- `tests/rei/test_local_model_language_policy.py`.

This branch does not merely add those paths. A clean synthetic merge would
modify 32 `app/` paths, six `scripts/` paths, and 24 `tests/` paths relative
to current main.

### Branch-only evidence

There are 360 branch-only evidence or evidence-document paths:

- EN1 frozen evidence root,
  `Docs/evals/semantic_lab_v1/en1-gemma4-text-shadow-2026-07-20/`
  (118 files);
- EN2 frozen evidence root,
  `Docs/evals/semantic_lab_v1/en2-gemma4-explained-shadow-2026-07-21/`
  (115 files);
- EN3 frozen evidence root,
  `Docs/evals/semantic_lab_v1/en3-gemma4-observable-shadow-2026-07-22/`
  (116 files);
- `gemma4_english_runtime_shadow_smoke.md`;
- EN1 receipt and seal;
- EN2 receipt and seal;
- `gemma4_explained_shadow_gui_2026-07-21.md`;
- `gemma4_observable_shadow_en3.md`;
- EN3 receipt and seal;
- `gemma4_shadow_gui_s2a.md`;
- `gemma4_shadow_gui_s2a1.md`.

The EN1 development smoke records two calls, zero retries, and zero fallbacks;
full Emocio abstention; an Instinkt action-only claim; valid DraftV3 and
canonical interpretation in both lanes; and an unchanged authoritative
cycle. EN2 records an Emocio draft-validation failure and an accepted
Instinkt result. EN3 preserves the exact bounded Emocio rejection and the
accepted Instinkt result. None is an untouched holdout, promotion decision,
or authority grant.

The branch adds `.gitattributes` rules that preserve EN1, EN2, and EN3 text
bytes and treat lock sentinels as binary. A synthetic merge retains the
main-side PR #6 C4 byte rules as well; those rules have no textual conflict.

### Expected conflicts and post-PR relevance

`git merge-tree --write-tree` completed without a textual conflict and
produced synthetic tree
`a3e42f7666b9f1e7b3e7cb97bf6408ef51a7b914`. That tree differs from current
main in 425 paths, with 11,500 insertions and 290 deletions. Of those paths,
349 are the three frozen EN evidence roots.

The absence of textual conflicts hides the following semantic reconciliation
requirements:

- the branch predates both PR #5 and PR #6 and therefore never evaluated its
  documentation or runtime descriptions against restored historical canon,
  restored plans, or the integrated inactive C4 review runtime;
- its `CURRENT.md` retains the 2026-07-19 heading, calls S2 future work even
  though the branch itself contains S2A/S2A.1, omits EN1–EN3 outcomes, and
  omits PR #5 and PR #6 entirely;
- its `research_log.md` adds only the 2026-07-20 language decision, not the
  later S2A.1, EN1, EN2, or EN3 executions;
- its selector hardcodes EN3 as `current_runtime`. That label is true only
  for the exact branch implementation and provider revision. It is false on
  current main, and it would become historical again if the English boundary
  is ported into a deduplicated provider with a new implementation identity;
- the branch creates parallel English packet, canonicalizer, native-provider,
  structured-interpreter, and Gemma-provider modules. Git identifies
  `ollama_gemma4_epistemic_en.py` as a 51% copy of the frozen V3 provider and
  the EN provider test as a 56% copy of the V3 provider test. The EN1 runner
  is a 34% copy of the S1 runner. This duplication was understandable as a
  way to avoid mutating frozen G3C code, but it is not a sound long-lived
  active architecture;
- direct integration would change broad model-backed and presentation
  behavior, which is outside MAIN-R1 and requires a separate reviewed
  integration phase.

The English-only dispatch policy, lack of implicit translation, provider
provenance, immutable evidence, and diagnostic-only authority boundary remain
meaningful after PR #5 and PR #6. The entire branch tree is not suitable for
unchanged integration.

**Branch recommendation: `port selectively`.** Preserve its ancestry and
frozen evidence, but do not accept its complete runtime tree as current
architecture.

## Required component reconciliation

| Component | Main / branch finding | Recommendation | Reason |
| --- | --- | --- | --- |
| S2A shadow GUI | Main has no shadow evidence tab. S2A adds loopback-only, read-only, allowlisted replay with no provider import or authority. Later commits supersede the original projection. | **port selectively** | Keep the endpoint, safety, authority, responsive-layout, and presentation separation contracts; port against current main and the final evidence schema instead of integrating the original S2A patch verbatim. |
| `shadow_view.py` | It is absent on main, grows from 1,029 lines in S2A to 1,725 lines on the English head, and combines registry, byte verification, privacy checks, cold verification, evidence decoding, and UI projection. | **port selectively** | The checks are valuable, but the monolith duplicates phase-specific projection logic and hardcodes currentness. Reuse small existing hashing/content-ID primitives and keep one data-driven registry; do not introduce a framework. |
| English local-model language boundary | Main still permits the frozen bilingual/Slovene-capable model-facing structures when an optional model path is explicitly used. The branch adds a strict metadata gate and changes many producers and adapters. | **port selectively** | The policy decision remains valid and prevents a return to the old bilingual active model boundary. Port one shared pre-dispatch `en` gate and exact provenance into active local-model entry points; do not copy every provider solely to change identity and instruction text. |
| English V3 packet/provider | The branch adds a second packet/canonicalizer stack and provider copies while preserving frozen G3C V3 files. | **port selectively** | Frozen G3C V3 code must remain unchanged, but a thin English active adapter should share stable validation/transport primitives. Retain English-only semantics and use a new exact implementation revision; do not present EN1–EN3 as evidence for that new revision. |
| EN1 smoke evidence | The sealed result is coherent, cold-closed, no-authority development evidence and is followed by EN2/EN3. | **integrate unchanged** | Preserve EN1 bytes, seal, receipt, report, and execution ancestry exactly. Classify it as historical evidence, not a current smoke of the deduplicated implementation. |
| EN1/EN2/EN3 execution runners | The runners are phase-specific, the EN1 runner copies S1 infrastructure, and EN2/EN3 mutate imported module globals to reconfigure it. The GUI evidence verifier does not need these provider-bearing runners to inspect the EN roots. | **abandon as superseded** | Keep the runner commits reachable in merge ancestry for provenance, but do not make these one-shot execution scripts part of the active main tree. Their evidence remains independently preserved. |
| Current/historical evidence selector | The final branch groups EN3 as current and EN2/EN1/S1/S1R as historical. | **port selectively** | Preserve explicit grouping and language labels, but compute “current” from an exact active implementation/provider revision match. With a deduplicated port, EN1–EN3 are all historical unless a separately executed smoke validates the new revision; MAIN-R1 authorizes no such smoke. |
| `CURRENT.md` | Main still describes the 2026-07-19 state and omits PR #5/#6. The branch version adds the language decision but is also dated 2026-07-19, calls S2 future work, and omits EN1–EN3 and PR #5/#6. | **port selectively** | Neither file is current enough to take unchanged. A later integration must author one fresh status from the post-integration tree, explicitly distinguish integrated code, historical evidence, inactive C4 infrastructure, and unstarted G4/C4 review. |
| `research_log.md` | Main ends at S1R-R. The branch adds only the initial English runtime language decision and omits the later S2/EN execution chronology. | **port selectively** | Preserve existing entries byte-for-byte where feasible, append the language decision and missing S2A/S2A.1/EN1/EN2/EN3 provenance, and never rewrite frozen reports as if later decisions existed at execution time. |

## Information architecture

### Canonical and historical knowledge

`knowledge/canon_v2/` is the active canonical architecture and semantic-lab
track. It contains the active acceptance, character, communication, Ego,
Emocio, Instinkt, Racio, glossary, open-question, evaluation, and frozen
semantic-lab artifacts. `README.md` already points active development to this
directory.

`knowledge/canon/` is a historical pre-native track. PR #5 restored several
missing files there and added explicit historical notices inside the restored
YAML. The merge result of either compared branch would retain these files;
the branch-vs-main diff showing them as deleted is only a two-tip tree diff,
not the result of Git's three-way merge.

The remaining information-architecture risk is naming and placement:
`scripts/validate_rei_canon_v2.py` reads `knowledge/canon/`, and active tests
under `tests/v2/` validate that historical track. Their names make
`knowledge/canon/` look like the active v2 source even though `README.md` and
the native architecture use `knowledge/canon_v2/`. A later documentation-only
cleanup should label this validator and suite as historical snapshot
integrity, or move their entry point under an explicitly historical namespace.
It must not rewrite either canon or change runtime loading.

### Historical plans

PR #5 correctly gives the restored research-reset, Gemma, G3, and post-G3
plans prominent `HISTORICAL`, `CLOSED`, `SUPERSEDED`, and `DO NOT EXECUTE`
headers. The older
`plans/REI_next_phases_merge_semantic_architecture_2026-07-14.md` begins with
`SUPERSEDED FOR FUTURE WORK`, and
`plans/REI_v3_Codex_first_execution_prompt.md` is also marked superseded.

Two top-level records remain easier to mistake for active instructions:

- `plans/CODEX_kickoff_archive_REI_v3_2026-07-13.md`;
- `plans/REI_native_composition_architecture_upgrade_2026-07-13.md`.

The second is still a useful architecture provenance record, but its
implementation has completed. A later information-architecture-only change
should add an unmistakable completed/historical execution banner while
retaining its role as architecture provenance. The first should be explicitly
marked completed/historical. Files already under `plans/archive/` are
historical by location, but a short archive index would make that boundary
more discoverable. None of these documentation changes belongs in MAIN-R1.

### `CURRENT.md`

`CURRENT.md` is not actually current at main
`8eddb2de68852aab4d4e7d29df090f81f5e73002`. It accurately preserves the
deterministic/default and no-authority boundaries, but it:

- is headed 2026-07-19;
- does not record PR #5's canonical/historical information architecture;
- does not record PR #6's integrated but inactive C4 Stage 1 review runtime;
- does not say that no C4 Stage 1 human review artifact has been issued;
- cannot claim the English boundary or S2 GUI as integrated because those
  remain only on unmerged branches;
- does not identify reconciliation as the gate before G4.

The English branch's `CURRENT.md` is not an acceptable replacement because
it is also stale and claims branch-only runtime semantics as active. Updating
`CURRENT.md` must be an explicit integration deliverable after the selected
tree is known, not a blind file-level merge.

### `research_log.md`

The main log is chronological through S1R-R. The English branch adds the
human decision for the English active model boundary but does not append the
actual EN1–EN3 or S2 presentation phases. Its existing entries should remain
historical records. The later integration should append missing decisions and
execution identities, including failures and no-authority qualifications,
without retroactively editing frozen evidence or treating technical smoke as
semantic acceptance.

## Minimal integration plan proposed for human review

No step below is authorized by MAIN-R1; this is a proposed next phase only.

1. Start a new reviewed integration branch from the then-current main. Do not
   merge `codex/racio-gemma4-shadow-gui` separately because its execution
   commit is already an ancestor of
   `codex/rei-english-runtime-smoke`.
2. Merge `codex/rei-english-runtime-smoke` with a real two-parent,
   non-squash, non-rebased, no-fast-forward integration commit, using
   `--no-commit` so the resulting tree can be reconciled before the merge
   commit is created. This preserves all 22 execution/evidence commit
   identities and both PR #5/#6 main identities.
3. Keep the three EN evidence roots, their seals, receipts, reports, and EN
   `.gitattributes` rules byte-for-byte unchanged. Verify their blob IDs
   against the source branch. Preserve all PR #6 C4 byte rules.
4. Retain from S2 only the reviewed read-only replay boundary and final
   presentation behavior. Reconcile `shadow_view.py`, server routes, UI, and
   focused tests against current main. Label EN1, EN2, EN3, S1, and S1R as
   historical unless an evidence manifest matches the exact active provider
   and implementation revision.
5. Port the English-only local-model policy through one shared pre-dispatch
   gate and thin active adapters. Keep the frozen G3C V3 packet/provider files
   untouched. Do not restore an active bilingual model runtime, do not copy
   whole providers merely to change language identity, and do not add a new
   provider/evaluation framework.
6. Exclude the phase-specific EN1/EN2/EN3 execution runners from the active
   merged tree while retaining their commits in ancestry. No new smoke, model
   call, dataset, evaluator, or framework is needed for integration.
7. Update `CURRENT.md` from the reconciled tree and append the missing
   chronology to `research_log.md`. Explicitly state that
   `knowledge/canon_v2/` is active, `knowledge/canon/` and completed plans are
   historical, C4 infrastructure is inactive with no issued review artifact,
   and G4 has not started.
8. Run model-free repository verification, evidence byte checks, GUI replay
   tests, and the canonical native cycle/profile matrix. Stop for human review
   before any G4 work, C4 review execution, PR, or merge to main.

This plan changes neither frozen evidence nor its historical claims. It uses
no squash or rebase, retains original execution commit identities through
merge ancestry, avoids the old bilingual active model runtime, introduces no
new framework, and leaves main in a reviewable state from which a separately
approved G4 phase can begin.

## MAIN-R1 validation

The required commands were run from the audit branch:

- `git diff --check`: passed, exit `0`, no output;
- `python -m pytest -q`: completed, exit `1`; `1311 passed`, `9 failed`,
  `684 errors` in `348.51s`;
- `python scripts/run_rei_native_cycle.py`: passed, exit `0`,
  `all_invariants_passed=true`, 45 stored artifacts, manifest SHA-256
  `5a63b2dcb731f4b05afdd5e621c19b7488414e868c3a4a21e0d421c4e988e117`;
- `python scripts/run_rei_native_profile_matrix.py`: passed, exit `0`, 12
  frozen bundles by 13 profiles, `b10_oracle_rows=156`,
  `native_processor_executions=0`, matrix SHA-256
  `b7249e1d4b4f7aeccdbb48718c1aaaf96e6ea49ed0d8f64b598ed7781974ee31`.

The exact pytest command did not expose 693 independent repository failures.
All 684 setup errors had the same environmental cause:
`PermissionError: [WinError 5]` while pytest enumerated
`C:\Users\Kotlet\AppData\Local\Temp\pytest-of-Kotlet`. This is the Windows
global-temp restriction already documented in `README.md`.

A diagnostic rerun with a repository-local `--basetemp` removed all 684 setup
errors and completed as `1918 passed, 86 failed` in `535.52s`. The 86
remaining failures were then fully reconciled:

- nine C3 official-pair tests rejected the audit checkout because a linked
  worktree represents `.git` as a file. The same nine tests passed in a short,
  clean local clone of audited main with an ordinary `.git` directory:
  `9 passed, 48 deselected`;
- 76 C4 review tests rejected a basetemp nested inside the repository because
  their contract requires state/runtime/browser roots outside the checkout.
  The four affected C4 files passed with an external writable basetemp:
  `106 passed`;
- one background telemetry sampler test observed its second sample before
  reading the initial status. Its immediate isolated rerun passed: `1 passed`.

These diagnostics made no source change and no model call. They account for
every failure in the local-basetemp run: the unchanged tests already supplied
1,918 passes, and all 86 failed cases passed under the path/topology each test
contract requires. The literal required pytest invocation remains recorded as
failed rather than being relabelled green.

Model calls during MAIN-R1: `0`.

## MAIN-R1 decision

- separate merge of `codex/racio-gemma4-shadow-gui`:
  **abandon as superseded**;
- unchanged merge of `codex/rei-english-runtime-smoke`:
  **rejected**;
- reviewed preservation of its ancestry and frozen evidence plus a
  deduplicated English/S2 port:
  **port selectively**;
- G4: **not started**;
- C4 review: **not started**;
- merge/cherry-pick/PR: **not performed**.

Stop after commit and push of this audit branch for human review.
