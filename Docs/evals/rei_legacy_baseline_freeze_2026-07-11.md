# REI Legacy Baseline Freeze — 2026-07-11

This record freezes the reproducible legacy comparison point before
canonical-v2 implementation. It documents existing behavior; it does not
promote the legacy weighted/situational logic into canon v2.

## Git Identity

- frozen runtime SHA:
  `995b572c893058c82d265d978a0391e317f1ea67`
- pre-implementation snapshot SHA:
  `05996b2b4a34cf6dd654e032d5dbc26bb5373ef0`
- branch: `codex/pre-canonical-v2-snapshot`
- upstream: `origin/codex/pre-canonical-v2-snapshot`
- upstream state at observation: local and remote snapshot were synchronized

The snapshot commit adds planning and draft dataset artifacts on top of the
runtime SHA; it does not change the legacy runtime code. The pre-implementation
working tree had no tracked modifications. The pre-existing untracked
`tmp/` directory was intentionally excluded.

## Legacy Runtime Contract

- baseline id: `rei-profile-matrix-156`
- contract: `rei-profile-matrix-156-v1`
- runner: `scripts/run_rei_profile_matrix.py`
- engine entrypoint: `ReiEngine.run_rei_cycle`
- provider: `ollama`
- model: `granite4.1:30b`
- context: `65536`
- GPU layers option: `999`
- matrix: 13 profiles x 12 scenarios = 156 cases

Required full-run command:

```powershell
$env:REI_OLLAMA_NUM_CTX = "65536"
$env:REI_OLLAMA_NUM_GPU = "999"
python scripts/run_rei_profile_matrix.py --model granite4.1:30b --num-ctx 65536 --num-gpu 999
```

The local full Granite reference is:

`output/reports/rei_profile_matrix/20260519_153731_granite4_1_30b_64k_gpu999_postfix/summary.md`

It records 156 cases, context 65536, GPU layers 999, and zero fallbacks.
Because `output/` is ignored, the committed
`Docs/evals/rei_profile_matrix_summary_2026-05-18.md` is the clone-visible
156-case summary. The committed 2026-05-19 daily summary has only 40 cases and
is not a full-baseline artifact.

## Observed Local Environment

Observation date: 2026-07-11.

- Python: `3.12.10`
- pytest: `9.1.1`
- Ollama runtime in WSL: `0.30.8`
- Ollama server: running
- model residency at observation: no model loaded
- `granite4.1:30b`: installed and available

The absence of a resident model means GPU placement was not observable at the
freeze instant. Full Granite runs must still send `num_gpu=999`; during the
known baseline setup this produced 100% GPU placement at context 65536.

Runtime observation commands:

```powershell
wsl ollama --version
wsl ollama ps
wsl ollama list
```

During a large-model run, confirm placement separately:

```powershell
wsl ollama ps
```

## Structural Test Inventory

The suite contained 11 test files:

1. `tests/test_acceptance.py`
2. `tests/test_ego_fields.py`
3. `tests/test_ft_dataset.py`
4. `tests/test_normalization.py`
5. `tests/test_processor_distinctness.py`
6. `tests/test_processor_eval.py`
7. `tests/test_profiles.py`
8. `tests/test_rei_canonical_contracts.py`
9. `tests/test_rei_cycle.py`
10. `tests/test_rei_cycle_regression_contract.py`
11. `tests/test_rei_profile_matrix.py`

Recorded result:

```text
60 passed, 3 subtests passed
```

Exact isolated command:

```powershell
uv run --no-project --with pytest==9.1.1 --with-requirements app/backend/requirements.txt python -m pytest -q --basetemp output/pytest-legacy-freeze-20260711
```

The explicit `--basetemp` keeps pytest's temporary files inside the ignored
`output/` boundary and avoids relying on the host's shared temporary
directory.

## Contract Verification

Command:

```powershell
python scripts/verify_rei_contract_pack.py
```

Recorded result:

```text
REI contract verification OK.
```

## Live Ollama Smoke Verification

After the Phase 0/1 data and documentation changes, the unchanged legacy
runner completed one real Ollama case:

```powershell
$env:REI_OLLAMA_NUM_CTX = "65536"
$env:REI_OLLAMA_NUM_GPU = "999"
python scripts/run_rei_profile_matrix.py `
  --provider ollama `
  --model granite4.1:30b `
  --num-ctx 65536 `
  --num-gpu 999 `
  --profile-filter R `
  --scenario-filter meeting_avoidance `
  --max-cases 1 `
  --output-dir tmp/legacy-ollama-smoke-final/run `
  --docs-summary-dir tmp/legacy-ollama-smoke-final/docs
```

Recorded result on 2026-07-11:

- cases: `1/1`;
- fallbacks: `0`;
- missing required keys: `0`;
- processor identity violations: `0`;
- resultant/leading mind: `racio` / `racio`;
- total tokens: `10187`;
- `wsl ollama ps`: `granite4.1:30b`, context `65536`, `100% GPU`.

The smoke artifacts remain under ignored `tmp/` and are not baseline canon.

## Phase 1 Structural Verification

After adding the data-only canon registry, glossary, validator, and tests, the
complete suite recorded:

```text
71 passed, 3 subtests passed
```

Both validation commands also passed:

```text
REI canon v2 validation OK.
REI contract verification OK.
```

This larger count includes the new Phase 1 validator tests; the frozen legacy
test inventory above remains the pre-implementation comparison point.

## Post-Phase Guard

After documentation and canon-v2 data work, the following command should show
no changes to behavior-bearing legacy files:

```powershell
git diff --exit-code 05996b2b4a34cf6dd654e032d5dbc26bb5373ef0 -- app/backend/rei/engine.py app/backend/rei/profiles.py app/backend/rei/acceptance.py app/backend/rei/prompts.py app/backend/rei/contract_loader.py knowledge/canon/processor_contracts.json knowledge/rei_knowledge_index.json
```

Then rerun the full structural suite and the legacy contract verifier. A new
156-case LLM run is optional for documentation-only changes; the live one-case
smoke above verifies that the frozen Ollama path remains executable.
