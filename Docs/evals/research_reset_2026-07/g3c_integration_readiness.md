# G3C integration readiness

## Scope and status

- Phase: M-G3C, PR preparation only.
- Accepted G3C head: `37940f815bff1b98bbee9d989d0ccb89c8ec8c6c`.
- Verified M-G3C implementation/status head before this documentation-only
  record: `e5006e777994dd31a973b338831e7f6748265db0`.
- V3 technical contract and provider implementation: accepted and frozen.
- Gemma: shadow-ready, inactive by default, not promoted.
- M-G3C model calls: `0`.

## Model-free verification

The authoritative full run used a fresh local clone with a regular `.git`
directory and the checkout EOL rules from the verified head.

- `git diff --check`: passed.
- `python -m pytest -q`: `1778 passed in 356.26s`; no skipped, xfailed,
  failed, or errored tests.
- `python scripts/run_rei_native_cycle.py`: passed; all invariants true,
  deterministic option `option_restore`, 45 stored artifacts, manifest hash
  `5a63b2dcb731f4b05afdd5e621c19b7488414e868c3a4a21e0d421c4e988e117`.
- `python scripts/run_rei_native_profile_matrix.py`: passed; 12 fixtures x 13
  profiles = 156 rows, 156 B10 oracle rows, zero native-processor executions,
  matrix hash
  `b7249e1d4b4f7aeccdbb48718c1aaaf96e6ea49ed0d8f64b598ed7781974ee31`.
- Archive boundary: the full suite passed; the focused archive/cutover group
  independently passed `8/8`.

The first linked-worktree diagnostic exposed two environment boundaries: C3
requires a regular `.git` directory, and raw-hashed frozen artifacts require
LF on Windows. The final run used a clean clone after the missing explicit EOL
pins were added; no frozen blob or semantic artifact was changed.

## No-authority verification

Existing tests prove that the default provider set is model-free, the default
engine completes with only deterministic providers, deterministic cycles replay
byte-for-byte, the no-provider interpreter path makes no external call, and
active runtime code cannot import the archive.

The focused V3 guard additionally proves that:

- a fresh active-runtime import and default engine construction load neither
  Ollama nor Gemma modules and attempt no external connection;
- Gemma V3 is not exported or instantiated by the default runtime;
- V3 provider/output symbols are absent from `CharacterAuthority`,
  `GovernanceMandate`, `ConsciousDecision`, `BehaviorResultant`, and MindWorld
  updater paths;
- the isolated V3 contract/evaluator/provider modules contain none of those
  authority symbols.

## CI, secrets, and evidence

- No model weights, LFS pointers, API keys, credentials, or private-key blocks
  are present in the PR tree.
- M-G3C/PR additions contain no machine-local absolute paths. Historical
  documentation already present on `main` retains its recorded local provenance.
- G3 and G3C evidence: 460/460 JSON files parse; no private thinking text, raw
  response envelope, hidden truth, evaluator gold, profile, or authority data
  leaked into provider/response evidence.
- Thinking is retained only as allowed presence/hash/byte-count/token-count
  metadata. Successful validated DraftV3 and structured output remain the
  permitted response evidence.

## Known limitations

- G3C is a development rerun, not an untouched holdout; it grants no
  generalization claim.
- Gemma has no governance, conscious-decision, behavior, or MindWorld
  authority. Active-interpreter promotion is not allowed.
- G4 untouched holdout remains required on a separate branch.
- LongCat visual results remain exploratory.
- Instinkt raw-scene understanding and Ego untagged-motif detection remain
  open.
- Text shadow integration is a later, separately reviewed infrastructure phase
  on a new branch.

## Rollback and PR plan

- Pre-branch `main` rollback baseline and merge-base:
  `5c53cad56f47e9d1f672038cd6bc2741e449de88`
  (`rei-v3-pre-research-reset-2026-07-16`).
- After merge, rollback must preserve history with
  `git revert -m 1 <merge-commit-sha>`; do not reset shared `main`.
- PR title: `Integrate Gemma 4 epistemic V3 research provider and evidence`.
- Target: `codex/racio-gemma4-epistemic-interpreter` -> `main`.
- Required merge method: **Create a merge commit**. Squash and rebase merges
  are forbidden.
