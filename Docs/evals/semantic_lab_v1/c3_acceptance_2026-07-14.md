# C3 Racio interpreter acceptance — 2026-07-14

## Outcome

**NOT ACCEPTED — architecture complete; model quality gate blocked.**

Phase C3 delivered the conscious-access boundary, strict structured interpreter
contracts, deterministic and Ollama-backed providers, model registry, frozen
bilingual benchmark, provenance closure and engine integration. All work was
performed directly on `main`, beginning after C2 at
`695c0c2e5658e87da5ef67a468a323cd349b30ff`.

No live model run passed every mandatory C3 quality gate. Consequently no
candidate is selected as a default or production interpreter, and C3 must not
be reported as a phase-level pass. The architecture remains usable for
explicit experimental providers and deterministic baselines, with no implicit
model activation.

## Delivered architecture

- A `ConsciousAccessFilter` exposes only manifested, policy-visible aliases and
  artifacts; native truth and acceptance lineage remain audit-only.
- Typed Racio interpreter input, output, provider and execution contracts reject
  unknown fields, out-of-scope aliases and fallback execution.
- Unsupported action and motive classifications use the explicit `unknown`
  enum; `null` is reserved for option abstention.
- A deterministic baseline and a one-call Ollama structured-text provider share
  the same packet boundary and strict output contract.
- Provider identity binds the exact model digest, Ollama version, instruction
  hash, JSON-schema hash, runtime parameters and request inputs.
- The v5 adapter adds typed, public-surface-only calibration constraints. Their
  derivation policy, constraint hash and full provider-payload hash are bound in
  every call spec, and output validation is fail-closed.
- Ollama reads `REI_OLLAMA_NUM_CTX` and `REI_OLLAMA_NUM_GPU`, maps the latter to
  `num_gpu`, records both values and can require full GPU placement.
- The engine persists the structured interpretation and its provider evidence;
  it has no hidden deterministic fallback when a model-backed provider fails.
- A registry records candidates only. It contains no `default`, `selected` or
  `production` model field.
- A manually authored, frozen 32-case bilingual benchmark evaluates option,
  action, motive, ambiguity, citation scope, leakage, mutation and provenance.

## Frozen benchmark identity

Every live run used the same byte-identical input files:

| Artifact | SHA-256 |
|---|---|
| `manifest.json` | `1cbb5607acc95426673feddb9891567b5a46e5f4988f8cc171a6636069bbab4b` |
| `public_cases.jsonl` | `cc7f0c7dc5530af06372090b966b29e57f391196935e24a8d9ac7055cdb4f0ec` |
| `gold.jsonl` | `32fcede3cd445a7ba3160ee1592ba4eb1822c9efa9d16735d334c213e7b973f1` |

The runner's scoped-source guard required all benchmark-affecting source paths
to be clean before assigning an official run ID. The user's unrelated working
tree overlay was not included in any source commit or benchmark identity.

## Live model results

All denominators are the frozen benchmark counts. `Valid` is strict structured
output validity. `Option`, `Action` and `Motive` cover the 16 unambiguous cases;
`Ambig.` covers the 16 ambiguous cases; `Biling.` covers 16 language pairs.

| Run | Source | Model | Valid | Option | Action | Motive | Ambig. | Biling. | Passed | Gate |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Granite original | `ee8aa3f` | `granite4.1:30b` | 32/32 | 14/16 | 16/16 | 2/16 | 13/16 | 14/16 | 15/32 | FAIL |
| Granite v2 | `4a8dbb3` | `granite4.1:30b` | 32/32 | 14/16 | 16/16 | 9/16 | 11/16 | 10/16 | 20/32 | FAIL |
| Granite v3 | `b49ce53` | `granite4.1:30b` | 32/32 | 14/16 | 16/16 | 8/16 | 8/16 | 14/16 | 16/32 | FAIL |
| Qwen2.5-VL structured | `b49ce53` | `qwen2.5vl:32b` | 32/32 | 15/16 | 8/16 | 13/16 | 2/16 | 10/16 | 8/32 | FAIL |
| Qwen3.5 original | `5c513a0` | `qwen3.5:27b` | 32/32 | 16/16 | 16/16 | 14/16 | 1/16 | 15/16 | 15/32 | FAIL |
| Qwen3.5 v4 | `68e9f44` | `qwen3.5:27b` | 32/32 | 16/16 | 16/16 | 14/16 | 5/16 | 15/16 | 19/32 | FAIL |
| Qwen3.5 v5 policy run | `683fef6` | `qwen3.5:27b` | 29/32 | 16/16 | 16/16 | 14/16 | 13/16 | 14/16 | 27/32 | FAIL |

Every run recorded zero hidden-truth leakage, zero profile leakage, zero input
mutation and zero provenance-scope failures. Those safety gates pass, but they
do not override the failed structural and semantic gates.

## Mandatory gate disposition

| Required C3 gate | Best observed result | Disposition |
|---|---:|---|
| Hidden native payload leakage | 0 in every run | PASS |
| Character/profile leakage | 0 in every run | PASS |
| Strict structured output | v5 29/32; earlier runs 32/32 | FAIL for final candidate |
| Unambiguous option accuracy above deterministic baseline | v5 16/16 versus baseline 0/16 | PASS |
| Low confidence/abstention on ambiguous cases | v5 13/16 | FAIL |
| Citations restricted to visible observations | v5 has 3 evaluator citation-scope failures caused by rejected/no-output cases; no bad citation is proven | FAIL |
| Native bundle mutation | 0 in every run | PASS |
| Slovene/English semantic consistency | v5 14/16 | FAIL |

## v5 interpretation and evidence boundary

The v5 run used provider revision
`rei-ollama-racio-interpreter-c3-v5;ollama=0.31.2`, calibration policy
`c3-conscious-access-calibration-v1`, instruction SHA-256
`c5ea5a0936bbab5e9bb481e53443eb9119cb5bf2c1d58737f3bb0214ebcfb1b0`
and source commit `683fef66ab96d1849c6daf3df60710db26188622`.

Three ambiguous cases (`c3_case_004`, `c3_case_015` and `c3_case_016`)
ended with `OllamaResponseError` and therefore produced no accepted output,
call record or response evidence. The current result schema retains only the
exception type, not a sanitized message or rejected raw response. It is thus
not possible to prove from these artifacts whether each individual failure was
JSON/schema rejection or fail-closed conscious-access rejection. They must not
be described as three citation hallucinations or three proven constraint
violations; the evaluator correctly counts them as invalid output, citation
scope failure and semantic gate failure.

Cases `c3_case_017` and `c3_case_018` produced valid, scoped output with the
correct option and action, but inferred `attachment` instead of the gold
`motor_pattern` motive. This accounts for the remaining two failed cases.

The v5 artifact hashes are:

| Artifact | SHA-256 |
|---|---|
| `results.jsonl` | `ca7d6e3e20a6198bf2dd6316d1f694d2cb709eb2973892e1f364f8c137108a39` |
| `baseline_results.jsonl` | `1289834b0fddcb171554fd85ed328de32c139894a3108fb78dfd7017099cbc7f` |
| `metrics.json` | `0c47be2249d379a289c5b0acfe348a0a2223ebde13427df4349411aef3fa21cc` |
| `provenance.json` | `46d27a501735cc7e2bf6a912ee495a7c6aa1342b52ab02da86193a723497127c` |

## GPU placement

The first six runs contain response evidence showing `100% GPU` at context
`65536` for all 32 calls. The v5 run contains the same evidence for all 29
accepted calls, with requested `num_gpu=999`; all 32 call specs also record
`num_gpu=999` and `require_full_gpu=true`. During v5 the operator additionally
observed `wsl ollama ps` reporting `qwen3.5:27b`, 19 GB, `100% GPU`, context
`65536`.

The three rejected v5 calls have no response evidence, so checked-in artifacts
prove full placement for 29/29 evidenced calls, not 32/32. The model was stopped
after evidence capture and `wsl ollama ps` returned an empty active-model list.

## Adaptive-run limitation

Only the original run for each model is an initial evaluation on this corpus.
Granite v2/v3 and Qwen3.5 v4/v5 were revised after inspecting earlier failures.
In particular, v5 exposes a deterministic conservative adapter policy that
directly states the required abstention values for publicly limited packets.
Its ambiguity score therefore measures compliance with that versioned adapter
policy; it is not an independent estimate of model ambiguity detection or
generalization.

No further prompt or policy tuning should use this same gold corpus as if it
were a fresh validation set. A future generalization claim requires a new,
precommitted and previously untouched holdout corpus.

## Validation performed

```powershell
app\backend\.venv\Scripts\python.exe -m pytest
# 801 passed in 35.93s

app\backend\.venv\Scripts\python.exe -m compileall -q `
  app\backend\rei\communication `
  app\backend\rei\providers\ollama_interpreter.py `
  app\backend\rei\evaluation\racio_interpreter_benchmark.py

app\backend\.venv\Scripts\python.exe scripts\run_racio_interpreter_benchmark.py `
  --mode ollama `
  --model-id qwen3.5:27b `
  --model-digest 7653528ba5cba4dd8e19da24aaddc7f4d0b5ecd93571c0825dfd4137958ec06e `
  --num-ctx 65536 --num-gpu 999 --require-full-gpu `
  --output-dir Docs\evals\semantic_lab_v1\c3-racio-interpreter-qwen3.5-27b-v5-2026-07-14
# quality_gate_pass=false; evidence preserved
```

The benchmark command returns a non-zero exit code when the quality gate fails;
that is the expected runner behavior and does not invalidate the evidence.

## Registry disposition

- `granite4.1:30b`: Slovene/English semantic lab benchmarked; rejected for the
  C3 structured-text role.
- `qwen3.5:27b`: Slovene/English semantic lab benchmarked; rejected for the C3
  structured-text role.
- `qwen2.5vl:32b`: structured-text run failed, but its registry status remains
  `vlm_adapter_candidate` because the visual adapter path was not tested.
- No default, selected or production model exists.

## Known limitations and unblock criteria

- There is no passing model-backed C3 candidate.
- v5 error evidence does not retain a sanitized rejection category or rejected
  response, limiting diagnosis of its three invalid outputs.
- The strict ambiguity policy is an implementation hypothesis, not an
  empirically established psychological threshold.
- The benchmark contains 32 handcrafted cases and is not a population-level
  language or cognition evaluation.
- The visual/VLM interpreter stage remains untested.

C3 model quality can be unblocked by evaluating a new candidate against the
frozen regression suite and a separately precommitted untouched holdout, while
preserving typed fail-closed constraints and recording a sanitized failure
category. C4 must not be presented as evidence that C3 passed; proceeding to C4
or opening another C3 candidate requires an explicit phase decision after this
planned quality-gate stop.

## Required phase report

```text
Phase: C3 — real RacioInterpreter
Branch: main
Base main SHA: 695c0c2e5658e87da5ef67a468a323cd349b30ff
Architecture status: complete
Model quality status: blocked; phase NOT ACCEPTED
Production/default model selected: no
Core commits: ee8aa3f, 4a8dbb3, b49ce53, 5c513a0, 68e9f44, 683fef6
Tests passed: 801 full repository tests
Tests failed: 0
Live model runs: 7
Live model quality gates passed: 0
Safety counters: 0 hidden leakage, 0 profile leakage, 0 input mutation, 0 provenance-scope failures in every run
Artifacts created: 28 immutable run files plus this acceptance report
Known blocker: no model satisfies all mandatory structural, ambiguity, citation and bilingual gates
Rollback path: git revert the scoped C3 commits in reverse order
Recommended next action: explicit review; choose a new precommitted C3 candidate/holdout or authorize C4 with C3 quality still open
```
