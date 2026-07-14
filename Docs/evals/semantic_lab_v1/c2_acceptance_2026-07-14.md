# C2 semantic evaluator acceptance — 2026-07-14

## Outcome

**PASS.** Phase C2 adds a deterministic, source-grounded semantic evaluator
for native routes, conscious interpretations, bilingual consistency and Ego
longitudinal composition. The phase changes no production processor path and
makes no provider or model call.

The phase started directly on `main` at
`1d606328656e833be5fc8ff3ac18655a573e3001`, reconciled with `origin/main`.

## Delivered scope

- typed candidate, trusted-case, exposure, result and run contracts;
- shared structural metrics plus Racio, Emocio and Instinkt route evaluators;
- communication evaluation for all eight interpretation labels using explicit
  trusted distortion evidence;
- structured Slovene/English signature and terminology evaluation;
- longitudinal Ego motif, continuity, projection and narrative-boundary
  evaluation;
- content-addressed blind-review commitments, one-way review ledger and typed
  reviewer-agreement evidence;
- deterministic, dimension-preserving reports with no global REI score;
- 32 manually authored positive and negative quality-gate cases;
- a pinned official manifest identity and six reproducible run artifacts.

## Quality-gate evidence

The 24 reported failures are the expected outcomes of the 24 intentionally
negative candidates. Quality-gate success means that the evaluator reproduced
all 32 reviewed decisions exactly; it does not mean that every candidate
passed semantic evaluation.

| Gate | Result |
|---|---:|
| Manual cases | 32 |
| Positive candidates | 8 |
| Negative candidates | 24 |
| Native-route cases | 16 |
| Interpretation cases | 8 |
| Bilingual cases | 3 |
| Ego-sequence cases | 5 |
| Exact evaluator decisions | 32 / 32 |
| Unexpected failed dimensions | 0 |
| Evaluator model calls | 0 |
| C1 canonical native routes evaluated | 304 / 304 passed |
| C1 interpretation variants evaluated | 192 |
| Accurate interpretation variants | 144 / 144 passed |
| Partial or unknown variants | 48 / 48 failed as expected |
| Focused evaluation tests | 84 passed |
| Full repository tests | 739 passed |

## Commands and results

```powershell
app\backend\.venv\Scripts\python.exe -m pytest tests\evaluation -q --basetemp .pytest_tmp_eval_final
# 84 passed in 2.37s

app\backend\.venv\Scripts\python.exe scripts\run_semantic_lab_evaluation.py
# 32 cases, 32 exact matches, 0 evaluator model calls, six artifacts created

app\backend\.venv\Scripts\python.exe scripts\run_semantic_lab_evaluation.py --check
# six checked-in artifacts reproduced byte-for-byte

app\backend\.venv\Scripts\python.exe -m compileall -q app\backend\rei\evaluation tests\evaluation scripts\run_semantic_lab_evaluation.py

app\backend\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest_tmp_full_c2
# 739 passed in 34.03s
```

## Frozen identity and artifact hashes

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `knowledge/canon_v2/evaluation.json` | — | `a212d46cc61cb043eb60ed443c830c528d86bb5b88e64be937494beddd9e89ed` |
| `knowledge/semantic_lab_v1/schemas/evaluation_case.schema.json` | — | `747efca145d0697872b60f347fe224892acc19669e0c320a23645d8e7c02ff74` |
| `tests/fixtures/semantic_evaluation_v1/manifest.json` | — | `a2aed73eac97d68b90236da15d214b6121c84378800e85764fc267dba75bc7cc` |
| `summary.md` | 13,798 | `9eaaf8d1b221b8b8880ba9d233cb8336f7b49204f6344ea58814835358a324c2` |
| `metrics.json` | 350,293 | `3cb01e0914919c6d266bbfc8572049108f51e9884246b66564ded52ce3bfc1c5` |
| `failures.jsonl` | 61,259 | `8213f5a82da69e38e3662227ca02244d8516687c2d1b744d682ac6ea7f958158` |
| `confusion_matrices.json` | 5,974 | `5334b02104539ab9d4eee35190e92542690a5fd25551c9df5629f58778b7f47b` |
| `bilingual_consistency.json` | 8,343 | `b64020781777f45be7bc88b4bec1ff0469c186e7226f16335671a1b3c95cdaa2` |
| `human_review_summary.md` | 1,941 | `50f5864ee232a72cbc2c8aa5ee2add1c4dda23d64893a3e17c13044010c5cbff` |

The runner accepts a byte-identical copy of the official fixture corpus but
rejects any re-signed alternative manifest before assigning the official
`c2-deterministic-2026-07-14` run ID.

## Safety and semantic boundaries

- Trusted input exposure is a separate content-addressed evaluator input; it
  cannot be supplied inside a candidate payload.
- Results bind both the trusted case and exact candidate-content hash, so an ID
  cannot replay a different payload unnoticed.
- Candidate fields never define trusted family, source-mind, visible-scope,
  native representation, terminology, Ego sequence or projection truth.
- Interpretation labels come from typed evaluator evidence. Candidate operation
  fields are checked for consistency but cannot select their own gold label.
- Native-route decisions use structured claims, provenance, evidence, option
  IDs and domain facets; production keywords are never the sole criterion.
- Blind review commits all material before first pass, reveals source and gold
  only through the one-way ledger transition, and rejects forged or branching
  transitions.
- Multi-reviewer agreement is reportable only as replay-valid typed evidence.
  Untyped reviewer counts cannot claim agreement.
- All dimensions remain separate. No global score or cross-dimension rank is
  computed.

## Known limitations

- C2 is deliberately model-free; it validates evaluator semantics before C3
  introduces model-backed interpretation.
- No two-reviewer blind-review dataset was supplied, so reviewer agreement is
  correctly reported as `not_applicable` rather than inferred.
- Per-case Brier error is an implementation hypothesis for consistency, not an
  empirical population-calibration claim.
- Structured bilingual signatures detect semantic drift but do not establish
  full natural-language translation quality; that remains a human-review task.
- The five Ego fixtures validate the executable contract but do not yet form a
  broad longitudinal benchmark.

## Required phase report

```text
Phase: C2 — semantic evaluator
Branch: main
Base main SHA: 1d606328656e833be5fc8ff3ac18655a573e3001
Head SHA: phase commit containing this report; a self-referential SHA is intentionally not embedded
Changed files: 2 tracked files (.gitattributes and knowledge/canon_v2/open_questions.md)
New files: 40 evaluator, policy, schema, fixture, test, runner and report files including this acceptance report
Deleted files: 0
Architecture changes: typed model-free semantic evaluation package, trusted exposure boundary, blind-review ledger and deterministic reporting
Runtime changes: none to production processors or providers; evaluation entrypoint only
Canon claims added: 0
Implementation hypotheses added: 4
Open questions added: 1 (OQ-EVAL-001)
Tests run: focused evaluation suite; deterministic report create/check; compileall; full repository suite
Tests passed: 84 focused; 739 full repository; 32/32 manual exact decisions
Tests failed: 0
Model-backed runs: 0
Artifacts created: six C2 run artifacts, acceptance report, evaluation policy, schema and manifest-bound fixtures
Known limitations: model-free, reviewer agreement N/A, per-case calibration not empirical, structured bilingual metric not full translation review
Regression risk: low-to-moderate and isolated to the new evaluation package; full suite is green
Rollback path: git revert <C2 phase commit>
Proposed commit: feat(eval): add semantic route and translation evaluation
Recommended next phase: C3 — real RacioInterpreter
```
