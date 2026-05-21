# REI Workbench GUI

This is the active prompt-testing GUI for the current REI baseline.

It is intentionally separate from the archived legacy GUI. The workbench reads
the current baseline prompts from `app/backend/rei/contract_loader.py`, allows
local prompt overrides, streams direct Ollama responses, and records local test
history.

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
