# Non-Baseline Archive 2026-05-21

This archive contains project surfaces that are not part of the current baseline evaluation entrypoint:

```powershell
python scripts\run_rei_profile_matrix.py --model granite4.1:30b --num-ctx 65536 --num-gpu 999
```

Baseline kept in the active tree:

- `scripts/run_rei_profile_matrix.py`
- `scripts/filter_rei_cases.py`
- `scripts/verify_rei_contract_pack.py`
- `scripts/stop_rei_run.ps1`
- `app/backend/rei/acceptance.py`
- `app/backend/rei/contract_loader.py`
- `app/backend/rei/engine.py`
- `app/backend/rei/json_utils.py`
- `app/backend/rei/knowledge.py`
- `app/backend/rei/models.py`
- `app/backend/rei/normalization.py`
- `app/backend/rei/processor_contracts.py`
- `app/backend/rei/processor_eval.py`
- `app/backend/rei/profiles.py`
- `app/backend/rei/prompts.py`
- `app/backend/rei/providers.py`
- `knowledge/`
- `Docs/evals/`
- baseline-related tests in `tests/`

Archived here:

- `app/frontend/`: previous browser UI and built assets.
- `app/backend/main.py`: previous FastAPI entrypoint.
- `app/backend/rei/playground.py`: previous playground adapter.
- `app/backend/rei/version_manifest.py`: previous runtime API manifest.
- `app/backend/rei/weighted_audit.py`: previous weighted-synthesis audit helper.
- non-baseline runner scripts: runtime matrix, role-drift probe, A/B sequence, older cycle matrix, processor matrix, and Granite weighted short runner.
- tests that exercised the archived UI/API/weighted-synthesis surfaces.
- `rei_v3_next_upgrade_patch_pack/`
- `arhiv nadgradenj/`
- `rei_app_spec.md`
- `examples/scenarios/quit_job_start_business.json`
- `prejsnji poskusi/` / `prejšnji poskusi/`
- root `trace.json`

Nothing in this archive is deleted. It is retained so old behavior can be inspected or restored deliberately, but it should not be treated as part of the active baseline.
