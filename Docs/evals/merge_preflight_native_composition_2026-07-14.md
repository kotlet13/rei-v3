# REI native-composition merge preflight — 2026-07-14

## Result

The preflight supports a non-squash merge of `origin/main` into
`codex/architecture/rei-native-composition`, followed by a merge-commit PR into
`main`. The branch graph is the expected 20-ahead/1-behind divergence and the
only commit unique to `main` is the historical canonical-v2 execution prompt.
`git merge-tree --write-tree` completed without a conflict.

No runtime file was changed during this phase.

## Source refs and branch graph

| Ref | SHA |
|---|---|
| `origin/main` | `07a26401e0b2707a79018efc2fdd7194d3062566` |
| `origin/codex/architecture/rei-native-composition` | `7bf7b23f23f3315c15b5b95a9456d4ce611e6ffb` |
| local `codex/architecture/rei-native-composition` before this report | `7bf7b23f23f3315c15b5b95a9456d4ce611e6ffb` |
| merge base | `995b572c893058c82d265d978a0391e317f1ea67` |

`git rev-list --left-right --count origin/main...origin/codex/architecture/rei-native-composition`
returned `1 20`: the architecture branch is 20 commits ahead and 1 commit
behind `origin/main`.

```text
* 7bf7b23 architecture/B14 acceptance (20-commit native-composition line)
* ...
* 05996b2 tagged textual baseline
| * 07a2640 origin/main: add canonical-v2 execution prompt
|/
* 995b572 merge base
```

There were no unexpected remote commits after `git fetch origin --prune
--tags`.

## Commit missing from the architecture branch

`07a26401e0b2707a79018efc2fdd7194d3062566` (`docs: add Codex canonical v2
execution prompt`) adds exactly one file:

```text
Docs/plans/REI_v3_Codex_first_execution_prompt.md
```

Its blob SHA is `0f3dccba1749e2d77591a5cb91ce00864ee10ab1`.
The content belongs to the superseded canonical-v2/QLoRA direction and must be
retained as history, not presented as the active implementation instruction.

## B14 and rollback verification

- B14 acceptance report exists at
  `Docs/evals/rei_native_architecture_acceptance_2026-07-13.md` and was committed
  by `7bf7b23f23f3315c15b5b95a9456d4ce611e6ffb`.
- The report records 632 controlled tests, 643 discoverable tests and the
  156-row frozen-native-bundle matrix.
- Annotated tag `rei-v3-text-llm-baseline-2026-07-13` resolves through tag
  object `ea04d0ef0da3bd3d6036eefbe552731a2083461e` to commit
  `05996b2b4a34cf6dd654e032d5dbc26bb5373ef0`.
- The safe rollback remains a separate worktree created from that tag; no tag
  movement, reset or force-push is required.
- B14 remains a historical acceptance record and must not be edited during
  integration.

## Dirty working tree

The tree was dirty before M0. Tracked overlays were present in:

```text
CURRENT.md
Docs/REI_weighted_synthesis_working_note.md
README.md
app/backend/requirements.txt
```

There were also untracked canonical-v2 review/canon files, the two 2026-07-14
execution plans, validator/tests and approximately 2.9 GB of untracked `tmp/`
test and review artifacts. B14 section 10 already identifies these as
user-owned dirty working-tree overlays and untracked canonical-v2 experiments,
preserved and excluded from B14 commits.

These files are not part of this integration. They must remain unstaged. In
particular, the local `CURRENT.md` and `README.md` overlays describe the old
canonical-v2 runtime direction and must not replace the accepted native
composition boundary.

The one commit unique to `main` does not overlap these dirty paths, and the
preflight merge simulation is clean. Continuing therefore does not require
discarding, rebasing or committing the user-owned overlay.

## Potential conflicts and duplicated documents

`git merge-tree --write-tree --messages origin/main
origin/codex/architecture/rei-native-composition` returned exit code 0 and
result tree `e2ecedbfa9066e3e574a93d38f6f7b64b5442a84`; no textual conflict was
reported.

The integration still has a semantic documentation duplication:

| Path | Status |
|---|---|
| `Docs/plans/REI_v3_Codex_first_execution_prompt.md` | Added by `main`; old prompt, currently unmarked |
| `plans/REI_v3_Codex_first_execution_prompt.md` | Same historical prompt with an existing superseded header |
| `plans/archive/REI_v3_Codex_first_execution_prompt.md` | Immutable historical copy; same blob as the `main` file |
| `archive/rei_v3_text_llm_baseline_2026-07-13/snapshot/plans/REI_v3_Codex_first_execution_prompt.md` | Frozen snapshot copy; do not edit |

M1 should add the prescribed `SUPERSEDED` notice only to the new
`Docs/plans/...` copy. It must not modify the archived copies or B14.

## GitHub state

- Open or closed PRs whose head is
  `codex/architecture/rei-native-composition`: none.
- Repository GitHub Actions workflows: none.
- A model-free CI workflow is therefore required in M2 before merging to
  `main`.

## Test plan

After merging `origin/main` into the architecture branch:

1. Run the complete discoverable suite with a repository-local `--basetemp`.
2. Run the controlled `tests/rei` plus archive/cutover guard suite.
3. Run `scripts/run_rei_native_cycle.py`.
4. Run the model-free `scripts/run_rei_native_profile_matrix.py`.
5. Run a loopback GUI smoke when the environment permits and check the Native,
   Communication, Character and Ego panels, mobile width and browser console.
6. Run the same model-free checks in GitHub Actions. CI must not contact
   Ollama, download renderer models or run QLoRA.
7. Repeat the complete suite and deterministic artifacts from merged `main`.

The canonical matrix is deliberately model-free. It must not be replaced by an
Ollama run. Any separate native Ollama smoke must explicitly use
`REI_OLLAMA_NUM_CTX=65536` and `REI_OLLAMA_NUM_GPU=999`, map `num_gpu` into the
provider options and record it in provenance.

## Recommended merge strategy

1. Commit only this M0 report.
2. Merge `origin/main` into the architecture branch with `--no-ff`; do not
   rebase or squash.
3. Mark the imported prompt superseded and add a new integration addendum;
   preserve B14 unchanged.
4. Add model-independent GitHub Actions coverage and push the architecture
   branch.
5. Open a PR to `main`, require green checks and use **Create a merge commit**.
6. Verify the resulting `main`, create the native-composition release tag and
   add the release record.

## Phase report

```text
Phase: M0 — pre-merge review
Branch: codex/architecture/rei-native-composition
Base main SHA: 07a26401e0b2707a79018efc2fdd7194d3062566
Head SHA: 7bf7b23f23f3315c15b5b95a9456d4ce611e6ffb (before report commit)
Changed files: Docs/evals/merge_preflight_native_composition_2026-07-14.md
New files: Docs/evals/merge_preflight_native_composition_2026-07-14.md
Deleted files: none
Architecture changes: none
Runtime changes: none
Canon claims added: none
Implementation hypotheses added: none
Open questions added: none
Tests run: git/ref/merge-tree diagnostics only; runtime tests deferred to M1
Tests passed: merge simulation exited 0
Tests failed: 0
Model-backed runs: none
Artifacts created: this report
Known limitations: no existing CI or PR; user-owned dirty overlay remains preserved
Regression risk: low for M0; no runtime changes
Rollback path: annotated tag rei-v3-text-llm-baseline-2026-07-13 in a separate worktree
Proposed commit: docs(integration): record native-composition merge preflight
Recommended next phase: M1 — merge origin/main into the architecture branch
```
