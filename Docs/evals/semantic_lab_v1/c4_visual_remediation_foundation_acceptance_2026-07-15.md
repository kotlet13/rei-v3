# C4 visual-remediation safety foundation acceptance — 2026-07-15

## Outcome

**THE MODEL-FREE C4 REMEDIATION SAFETY FOUNDATION IS INTEGRATED ON `main`;
MODEL INFERENCE, AUTHORITATIVE HUMAN REVIEW AND VISUAL-INFLUENCE AUTHORITY
REMAIN BLOCKED.**

Commit `303da44bf7d240dc91ae39e5ff3331ad8112fca1` adds the fail-closed
boundaries required before Stage 1 provider integration: a content-addressed
blind-review protocol, hard Windows process-tree ownership and bounded resource
telemetry. It does not load or invoke LongCat, OmniGen or any other model.

The repository remains at the pre-inference boundary defined by
[`c4_visual_remediation_protocol_2026-07-15.md`](./c4_visual_remediation_protocol_2026-07-15.md).
A separate, reviewed Stage 1 integration must still bind verified snapshots,
exact provider call specifications, durable background telemetry and the exact
PNG bytes displayed to the reviewer.

## Phase record

```text
Phase: C4 controlled visual-remediation safety foundation
Branch: main
Base main SHA: 71becac849fce4e7af2f03453696d0cd025badd8
Head SHA: 303da44bf7d240dc91ae39e5ff3331ad8112fca1
Changed files: app/backend/rei/evaluation/__init__.py; knowledge/canon_v2/open_questions.md
New files: app/backend/rei/evaluation/c4_blind_review.py; app/backend/rei/evaluation/process_start_bootstrap.py; app/backend/rei/evaluation/process_tree_runner.py; app/backend/rei/evaluation/resource_telemetry.py; tests/evaluation/test_process_tree_runner.py; tests/evaluation/test_resource_telemetry.py; tests/rei/test_c4_blind_review.py
Deleted files: none
Architecture changes: fail-closed C4 blind-review boundary; parent-owned bounded process-tree runner; uniform bounded resource-telemetry contracts
Runtime changes: authoritative Windows Job Object ownership and kill-on-close; start-gated child launch; bounded output/observer cleanup; sampled process-tree/system/CUDA telemetry; no provider adapter and no model call
Canon claims added: none
Implementation hypotheses added: C4 remediation operationalization and its explicit non-authority, sampled-telemetry and external-attestation limits
Open questions added: immutable displayed-byte receipt; durable background-telemetry finalization; covert external identifier boundary; sampled peak limitations
Tests run: scoped C4/runner/telemetry tests; all tests/evaluation; all tests/rei; compileall; Ruff check and format check; staged diff check; independent security/API audit
Tests passed: 177 scoped on the final state; 312 evaluation on the final state; 1075 REI regression tests; all static and audit checks
Tests failed: 0
Model-backed runs: 0
Artifacts created: four implementation modules, three regression modules, package exports, one implementation-hypothesis update and this acceptance report; no generated model artifact
Known limitations: no Stage 1 provider integration; no immutable-display receipt; no durable background-sampler finalization; no model output; no semantic or production authority; authoritative process-tree execution is Windows-only and POSIX launch refuses
Regression risk: Windows process/job teardown, hostile thread-start side effects, bounded PNG parsing and sampled telemetry; covered by adversarial regressions and an independent no-P0/P1/P2 signoff
Rollback path: normal revert of 303da44 and this documentation commit on main; no history rewrite, force-push or branch recreation
Proposed commit: feat(eval): add C4 remediation safety foundations
Recommended next phase: model-free Stage 1 provider/display/telemetry integration, committed and reviewed before any inference
```

## Accepted foundation scope

The accepted blind-review layer provides:

- exact content-addressed schema, material commitment, blind packet,
  presentation manifest, external operator policy, attestation, one-time ledger
  receipt, sealed submission, fail-closed gate and post-submission reveal;
- deterministic pair order derived from full blind-code SHA-256 values;
- exact source/output PNG hashing with an allowlist containing only `IHDR`,
  `IDAT` and `IEND`, bounded dimensions, byte size, decoded size and chunk
  count, streaming zlib validation and scanline-filter verification;
- a single bounded regular-file handle read with pre/post handle and path
  identity/size checks, rather than an unbounded path re-read;
- mandatory live HMAC-secret and external-ledger re-verification before a
  sealed receipt can carry runtime authority;
- literal `false` fields for semantic quality, production authority, human-
  cognition proof, displayed-byte execution attestation and model-judge use.

The accepted process boundary provides:

- an authoritative Windows Job Object with kill-on-close and exact active PID
  membership checks;
- a stdlib-only start-gate bootstrap that receives bounded argv, environment,
  working directory and deadline data only after containment assignment;
- retained-process-handle cleanup before Job assignment, avoiding raw-PID
  emergency termination and PID-reuse ambiguity;
- bounded stdout/stderr capture with full observed hashes, prefix hashes,
  truncation and stream-completeness provenance;
- bounded observer dispatch and full post-spawn cleanup across ordinary
  exceptions, `KeyboardInterrupt`, `SystemExit`, thread-start side effects and
  injected clock/process failures;
- explicit refusal to launch a workload where an authoritative POSIX
  containment implementation is unavailable.

The accepted telemetry layer provides:

- strict measured/unavailable readings and explicit measurement, subject and
  process scopes;
- PID plus live start-token binding, with a hash of the live Python executable;
- sampled Windows Job process-tree RSS, system-memory and exact UUID/PCI-bus
  CUDA-device readings;
- separate availability and capacity coverage, bounded sample/artifact counts
  and content-addressed serialization;
- a bounded `nvidia-smi` helper that reaps the child, closes pipes and joins
  every reader across timeout, output overflow and thread construction/start
  failures;
- monotonic terminal state for the background sampler without catch-up bursts.

## Verification evidence

The final scoped command covered all three new boundaries together:

```powershell
python -m pytest `
  tests/rei/test_c4_blind_review.py `
  tests/evaluation/test_process_tree_runner.py `
  tests/evaluation/test_resource_telemetry.py `
  -q -W error
```

Result: **177 passed**.

The final evaluation regression command was:

```powershell
python -m pytest tests/evaluation -q -W error
```

Result: **312 passed**.

The complete REI regression suite was also run during foundation closure:

```powershell
python -m pytest tests/rei -q -W error
```

Result: **1075 passed**. The later audit-only dispatcher correction changed
only `process_tree_runner.py` and its evaluation test; the final scoped and
complete evaluation runs above were repeated after that correction.

Additional checks passed:

- `compileall` for all eight scoped Python files;
- Ruff check and format check for all eight scoped Python files;
- staged whitespace/diff check for all nine scoped files;
- public API parity: 52 C4, 28 runner and 39 telemetry exports, with 183 unique
  package exports and no missing or mismatched symbol;
- independent final audit: no outstanding P0, P1 or P2 finding;
- no live start-gate bootstrap remained after testing;
- the pre-existing `WindowsTerminal` PID set was unchanged across the focused,
  evaluation and full REI runs.

## Explicit non-authority boundary

This acceptance does not authorize a first model call. In particular:

- `presentation_ui_execution_attested` remains `false`;
- `cold_validation_reverifies_exact_png_bytes` remains `false`;
- a manifest records historical PNG bytes but does not prove that those exact
  bytes were later displayed to the reviewer;
- the background sampler is not yet finalized into the durable per-run
  telemetry artifact;
- sampled process RSS and whole-device CUDA peaks are lower bounds, not proof
  that a transient limit was never crossed or that CUDA use belonged only to
  the child tree;
- external text identifiers remain a trusted-caller boundary and can encode
  data that direct raw/UTF-8/hex secret-material rejection does not recognize;
- no semantic quality or production visual-influence authority is granted.

The next phase must remain model-free until the exact provider adapters,
verified snapshot/file manifests, content-addressed pipeline specifications,
durable telemetry finalization and immutable displayed-byte receipt are
implemented, tested, committed and pushed to `main`. Review is required again
before inference.
