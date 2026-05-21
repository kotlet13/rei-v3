# REI v3

REI v3 is currently organized around the 156-case profile matrix baseline.

See [CURRENT.md](CURRENT.md) for the active boundary.

## Active Baseline

Run the baseline matrix:

```powershell
$env:REI_OLLAMA_NUM_CTX = "65536"
$env:REI_OLLAMA_NUM_GPU = "999"
python scripts\run_rei_profile_matrix.py --model granite4.1:30b --num-ctx 65536 --num-gpu 999
```

Baseline shape:

- 13 profiles
- 12 scenarios
- 156 cases
- active engine path: `ReiEngine.run_rei_cycle`
- summary copy: `Docs/evals/rei_profile_matrix_summary_{YYYY-MM-DD}.md`

## Active Code

The baseline uses:

- `scripts/run_rei_profile_matrix.py`
- `app/backend/rei/`
- `knowledge/`
- `Docs/evals/`

Useful support scripts:

- `scripts/filter_rei_cases.py`
- `scripts/verify_rei_contract_pack.py`
- `scripts/stop_rei_run.ps1`

## Archived Surfaces

The old UI/API/playground surfaces and non-baseline runners are archived at:

- `archive/non_baseline_2026-05-21/`

This includes the browser UI, previous FastAPI entrypoint, playground adapter, runtime manifest API, older eval runners, weighted-synthesis audit helpers, old tests for those surfaces, old API/UI specs, and old REI v2/reference material.

They are retained for inspection, not active execution.
