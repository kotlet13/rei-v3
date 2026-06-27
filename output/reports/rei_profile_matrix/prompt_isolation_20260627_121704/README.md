# REI Profile Matrix Results

Run: `prompt_isolation_20260627_121704`

This run evaluates the tightened processor prompt isolation rules with `gemma4:26b`.

- Profiles: 13
- Scenarios: 12
- Cases: 156
- Final processor identity violations: 0
- Fallbacks: 1

Start review with:

- `summary.md` for the readable aggregate report
- `summary.json` for scenario/profile distributions
- `cases.jsonl` for individual case records
- `cases.json` for the same records as a JSON array
- `progress.log` for chronological run progress

Note: the aggregate `missing_required_key_case_count` includes raw LLM calls that were repaired during the run. The final case payloads had no missing required keys when checked from `cases.jsonl`.
