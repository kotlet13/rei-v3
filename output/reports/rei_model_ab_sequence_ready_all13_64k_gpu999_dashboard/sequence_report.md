# REI Model A/B/C Sequence

## Run

- **run_id:** `20260516_084343`
- **num_ctx:** `65536`
- **num_gpu:** `999`
- **models:** `granite4.1:30b, gemma4:31b, qwen3.6:35b`
- **profiles_preset:** `all`
- **profiles_count:** `13`
- **estimated_total_cases:** `312`
- **live_mode:** `dashboard`
- **status:** `interrupted`

## Results

| Model | Return | Cases | Fallbacks | Avg drift R/E/I | Avg max overlap | Repetition hits | Report |
| --- | ---: | ---: | ---: | --- | ---: | --- | --- |
| `granite4.1:30b` | `1` | `0` | `0` | `-/-/-` | `0.0` | `{}` | `output/reports/rei_model_ab_sequence_ready_all13_64k_gpu999_dashboard/granite4_1_30b/report.md` |

## Output Files

- **plan:** `output\reports\rei_model_ab_sequence_ready_all13_64k_gpu999_dashboard\sequence_plan.json`
- **summary:** `output\reports\rei_model_ab_sequence_ready_all13_64k_gpu999_dashboard\sequence_summary.json`
- **report:** `output\reports\rei_model_ab_sequence_ready_all13_64k_gpu999_dashboard\sequence_report.md`
- **progress:** `output\reports\rei_model_ab_sequence_ready_all13_64k_gpu999_dashboard\sequence_progress.log`
- **synthesis_jsonl:** `output\reports\rei_model_ab_sequence_ready_all13_64k_gpu999_dashboard\sequence_synthesis.jsonl`
- **synthesis_report:** `output\reports\rei_model_ab_sequence_ready_all13_64k_gpu999_dashboard\sequence_synthesis_report.md`