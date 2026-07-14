# REI Native Composition — integration addendum

**Date:** 2026-07-14  
**Phase:** M1 — reconcile `main` into the accepted architecture branch  
**Status:** local integration verification passed

This addendum records integration evidence after B14. It does not modify or
reinterpret the historical B14 acceptance record at
`Docs/evals/rei_native_architecture_acceptance_2026-07-13.md`.

## Source and merge identity

| Item | SHA |
|---|---|
| Remote architecture head before M0 | `7bf7b23f23f3315c15b5b95a9456d4ce611e6ffb` |
| Architecture head immediately before the merge | `3a31e86b832932ab0efc75f04bf32efbfeee4ab2` |
| Imported `origin/main` head | `07a26401e0b2707a79018efc2fdd7194d3062566` |
| Merge base | `995b572c893058c82d265d978a0391e317f1ea67` |
| M1 merge commit | `3caa30536ac380675dde76f2d485f27cb0e0cb6b` |

The merge used `--no-ff` and preserved both parents. No rebase, squash,
force-push or tag movement occurred.

## Content imported from `main`

Commit `07a2640` added one historical document:

```text
Docs/plans/REI_v3_Codex_first_execution_prompt.md
```

The document belongs to the superseded canonical-v2/QLoRA direction. Its
historical body was retained and a prominent `SUPERSEDED` header now directs
readers to the active native-composition architecture, its implementation plan
and B14 acceptance record. Frozen copies under `plans/archive/` and
`archive/rei_v3_text_llm_baseline_2026-07-13/` were not changed.

## Runtime and architecture scope

M1 intentionally changed no runtime, processor, fixture oracle, provider,
model, renderer or training path. The accepted native-composition invariants
remain unchanged. The user-owned dirty canonical-v2 overlay documented in B14
remained unstaged and excluded from the integration commits.

## Verification evidence

All successful Python checks used the repository environment at
`app/backend/.venv` with Python 3.11.15, pytest 9.1.1 and Pydantic 2.13.4.

| Check | Result |
|---|---|
| Complete discoverable suite | `643 passed in 31.30s` |
| Controlled native/archive/cutover suite | `632 passed in 29.41s` |
| `scripts/run_rei_native_cycle.py` | exit 0; all invariants passed; 45 stored artifacts |
| `scripts/run_rei_native_profile_matrix.py` | exit 0; 156 rows; 12 fixtures; 13 profiles; 0 native processor executions |
| Matrix coverage | 156 B10 oracle rows; 36 pair-conflict rows; 9 thirteenth-majority rows; 13 simulated-spoznanje rows |
| Matrix hash | `b7249e1d4b4f7aeccdbb48718c1aaaf96e6ea49ed0d8f64b598ed7781974ee31` |

The first literal `python -m pytest` attempt selected an unrelated global
`document-agent` Python without pytest and therefore collected no tests. It was
an environment bootstrap error, not a test failure; all prescribed suites were
then run successfully in the repository environment.

The canonical 12 × 13 matrix remained model-free and did not contact Ollama.
No model-backed run was performed in M1.

## GUI smoke

The active GUI was served loopback-only and exercised in Microsoft Edge through
Playwright CLI. Port 8765 was already occupied by an unrelated local process,
so the REI smoke used `127.0.0.1:8766` without disturbing that process.

- the deterministic GUI cycle completed and reported all invariants passed;
- Native, Communication, Character and Ego panels rendered their expected
  content;
- evaluator debug exposed the native truth boundary and remained explicitly
  separated from Racio's visible interpretation;
- the B14 mobile acceptance scenario at 390 × 844 (debug Communication) had
  document width 390, body width 390 and no horizontal overflow;
- all observed application requests returned HTTP 200;
- browser console reported 0 errors and 0 warnings.

Local, ignored smoke artifacts:

```text
output/playwright/merge-preflight-2026-07-14/communication-debug-mobile.png
output/playwright/merge-preflight-2026-07-14/ego-mobile.png
```

Known GUI limitation: the Ego panel at 390 px measured a 459 px document width
because long trace/projection identifiers do not always wrap. This did not
affect the B14 debug Communication acceptance scenario and was not introduced
by the documentation-only merge. It is recorded for a later GUI-specific
phase; M1 deliberately made no runtime or CSS change.

The preferred in-app browser bootstrap was unavailable because its local
runtime failed initialization with `Cannot redefine property: process`.
Playwright CLI with Microsoft Edge provided the real-browser fallback evidence.

## GitHub Actions status

No GitHub Actions workflow existed during M1, and there was no open PR for the
architecture branch. Phase M2 must add model-independent CI for the controlled
suite, full discovery and deterministic artifacts before the branch is merged
into `main`.

## Phase report

```text
Phase: M1 — merge main into the architecture branch
Branch: codex/architecture/rei-native-composition
Base main SHA: 07a26401e0b2707a79018efc2fdd7194d3062566
Head SHA: 3caa30536ac380675dde76f2d485f27cb0e0cb6b (before docs commit)
Changed files: Docs/plans/REI_v3_Codex_first_execution_prompt.md; this addendum
New files: Docs/evals/rei_native_architecture_integration_addendum_2026-07-14.md
Deleted files: none
Architecture changes: none
Runtime changes: none
Canon claims added: none
Implementation hypotheses added: none
Open questions added: none
Tests run: full pytest; controlled pytest; native cycle; native profile matrix; GUI smoke
Tests passed: 643 full; 632 controlled; both deterministic runners and GUI smoke
Tests failed: 0 (one unrelated global-Python bootstrap attempt collected no tests)
Model-backed runs: none
Artifacts created: deterministic run/matrix outputs and ignored GUI screenshots
Known limitations: no CI yet; Ego mobile long-ID overflow; user-owned dirty overlay preserved
Regression risk: low; merge and follow-up are documentation-only
Rollback path: tag rei-v3-text-llm-baseline-2026-07-13 in a separate worktree
Proposed commit: docs(integration): mark canonical-v2 prompt superseded and record merge verification
Recommended next phase: M2 — model-independent CI and PR into main
```
