# REI Profile Matrix GUI Review Dataset

This dataset is imported from:

`output/reports/rei_profile_matrix/prompt_isolation_20260627_121704/cases.jsonl`

Purpose:

- Human review in the GUI dataset editor
- Not a training dataset
- Not exported to SFT JSONL

Shape:

- 12 scenarios
- 13 character profiles per scenario
- 4 review examples per scenario/profile: Racio, Emocio, Instinkt, EgoResultant
- 624 examples total

GUI review:

```powershell
python -m uvicorn app.gui.server:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`, select dataset
`rei_profile_matrix_review_20260627_121704`, then use the Target/Profile filters.

The examples have `generation_settings.review_only=true`. Validation skips the
fine-tune `process_trace` requirement for these imported runtime outputs, and
SFT export skips them even if their status is changed to `approved`.
