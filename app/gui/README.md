# REI Workbench GUI

This is the active prompt-testing GUI for the current REI baseline.

It is intentionally separate from the archived legacy GUI. The workbench reads
the current baseline prompts from `app/backend/rei/contract_loader.py`, allows
local prompt overrides, streams direct Ollama responses, and records local test
history.

Each output panel has a `View` selector. `RAW JSON` shows the complete raw model
response. Other options are discovered dynamically from the top-level keys in
the actual JSON output, including partial or truncated raw output where possible.
The selected view is remembered locally per processor.

Run:

```powershell
python -m uvicorn app.gui.server:app --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

Runtime files are ignored by git:

- `app/gui/data/prompt_overrides.json`
- `app/gui/data/test_history.jsonl`

The baseline runner remains `scripts/run_rei_profile_matrix.py`.

## Dataset Review

The workbench also exposes a local dataset editor for REI fine-tune datasets
under `datasets/{dataset_id}`. It can list examples, validate required REI
keys plus `process_trace`, edit assistant JSON, approve/reject examples, and
export approved valid examples to SFT chat JSONL.

Pilot generation is explicit and does not run from the GUI:

```powershell
python scripts\generate_rei_ft_dataset.py --dataset-id rei_ft_profile_pilot_v1 --model gemma4:26b --scenario-count 10 --dry-run
python scripts\generate_rei_ft_dataset.py --dataset-id rei_ft_profile_pilot_v1 --model gemma4:26b --scenario-count 10 --confirm-run
```

The default pilot shape is 10 matched situations. Each situation gets one
Racio, Emocio, and Instinkt example, then 13 EgoResultant examples over the
same processor signals, one per character profile.

Validation and export:

```powershell
python scripts\validate_rei_ft_dataset.py rei_ft_profile_pilot_v1
python scripts\export_rei_ft_dataset.py rei_ft_profile_pilot_v1
```

## Profile Matrix Review

Profile-matrix run outputs can be imported into the same dataset editor as
review-only datasets:

```powershell
python scripts\import_rei_profile_matrix_review_dataset.py output\reports\rei_profile_matrix\prompt_isolation_20260627_121704\cases.jsonl --dataset-id rei_profile_matrix_review_20260627_121704 --overwrite
```

The committed review dataset `rei_profile_matrix_review_20260627_121704`
contains 624 examples: 12 scenarios x 13 profiles x 4 targets. Use the GUI
Target and Profile filters to inspect one processor/profile combination at a
time. Review-only examples are skipped by SFT export.
