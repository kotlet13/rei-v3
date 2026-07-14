# C1 semantic laboratory acceptance — 2026-07-14

## Outcome

**PASS.** Phase C1 adds a deterministic, source-grounded evaluation corpus for
native REI routes. It does not change runtime processor behavior, call a model,
or expose a training/export entrypoint.

The phase started from fresh `main` commit
`3a293149053d68420fac4fff76c92c96db9de93b` on branch
`codex/semantic-lab-v1`.

## Delivered scope

- 24 required semantic scenario families;
- 8 grouped variants per family, 192 variants total;
- Slovene canonical inputs plus English operational glosses;
- canonical Racio, Emocio and Instinkt route expectations with grounded
  evidence and valid option references;
- Racio interpretation variants for visible Emocio and Instinkt
  manifestations;
- 28 canonical claim references in the semantic source index;
- 24 terminal `canon_approved` review events;
- four JSON schemas, including the longitudinal-sequence contract;
- 24 immutable family fixtures plus one fixture manifest;
- a deterministic build/check command and 12 focused acceptance tests.

## Quality-gate evidence

| Gate | Result |
|---|---:|
| Scenario families | 24 |
| Variants per family | 8 |
| Total variants | 192 |
| Canonical claim references | 28 |
| Source-traceable families | 24 / 24 |
| `canon_approved` families | 24 / 24 |
| Unapproved generated fixtures | 0 |
| Model-generated gold records | 0 |
| Model calls during generation | 0 |
| Training entrypoints/exports | 0 |
| Focused tests | 12 passed |
| Full repository tests | 655 passed |

Generated fixture evidence:

```text
source_hash = 7a12bea9251513cdb01d98d2ec802601f526ee69a84d33988b420be3f049b12f
fixture_manifest_sha256 = c22a299afc3063d7edf338d738396c18ca9298081d17374e4a1b153b3fad606e
generated_json_files = 25
generated_fixture_bytes = 812959
```

## Commands and results

```powershell
app\backend\.venv\Scripts\python.exe scripts\build_semantic_lab_fixtures.py --check
# 24 families, 192 variants, 25 files, 0 model calls, 0 training exports

app\backend\.venv\Scripts\python.exe -m pytest tests\semantic_lab -q
# 12 passed in 0.35s

app\backend\.venv\Scripts\python.exe -m pytest -q --basetemp <isolated-local-path>
# 655 passed in 31.25s
```

The first full-suite attempt used pytest's default user temp root. It completed
605 tests and reported 50 setup errors because Windows denied access to
`C:\Users\Kotlet\AppData\Local\Temp\pytest-of-Kotlet`. Repeating the same suite
with an isolated repository-local `--basetemp` produced the clean result above;
the temporary directory was removed after the run.

## Safety and semantic boundaries

- All generated evidence is supplied and grounded; generated fixture gold is
  derived from reviewed source records.
- Every family explicitly forbids behavior-to-character inference and profile
  leakage.
- Native route reasons remain distinct from the shared external behavior or
  option where the scenario requires that contrast.
- Expected answers are fixture-side evaluation truth, not model prompt text.
- Slovene is authoritative. English text is only an operational consistency
  gloss.
- The corpus is evaluation-only: no SFT, LoRA, QLoRA, train/validation split,
  provider call, or model dependency was introduced.

## Known limitations and next boundary

- C1 supplies canonical cases and deterministic validation, not semantic
  scoring. Route/translation metrics belong to C2.
- Interpretation fixtures represent expected evaluator truth; no model-backed
  Racio interpreter is introduced here.
- The longitudinal sequence schema is present, while executable longitudinal
  evaluation remains a later phase.
- Canonical approval is recorded in the append-only review log; future source
  changes must create new review evidence and regenerate fixture hashes.

Per the phase rule, implementation stops after this C1 report and commit. C2 is
not started pending review.
