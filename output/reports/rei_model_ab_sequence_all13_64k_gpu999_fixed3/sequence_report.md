# REI Model A/B/C Sequence

## Run

- **run_id:** `20260516_090517`
- **num_ctx:** `65536`
- **num_gpu:** `999`
- **models:** `granite4.1:30b, gemma4:31b, qwen3.6:35b`
- **profiles_preset:** `all`
- **profiles_count:** `13`
- **estimated_total_cases:** `312`
- **live_mode:** `dashboard`
- **status:** `completed`

## Results

| Model | Return | Cases | Fallbacks | Avg drift R/E/I | Avg max overlap | Repetition hits | Report |
| --- | ---: | ---: | ---: | --- | ---: | --- | --- |
| `granite4.1:30b` | `0` | `104` | `0` | `0.3677/0.0569/0.1759` | `0.1485` | `{"bounded test": 204, "minimum safety condition": 4, "responsible planning": 13}` | `output/reports/rei_model_ab_sequence_all13_64k_gpu999_fixed3/granite4_1_30b/report.md` |
| `gemma4:31b` | `0` | `104` | `0` | `0.3078/0.0187/0.1083` | `0.1287` | `{"bounded test": 166, "minimum safety condition": 4, "responsible planning": 22}` | `output/reports/rei_model_ab_sequence_all13_64k_gpu999_fixed3/gemma4_31b/report.md` |
| `qwen3.6:35b` | `0` | `104` | `0` | `0.2019/0.0175/0.1336` | `0.0904` | `{"bounded test": 206, "minimum safety condition": 4, "responsible planning": 10}` | `output/reports/rei_model_ab_sequence_all13_64k_gpu999_fixed3/qwen3_6_35b/report.md` |

## Output Files

- **plan:** `output\reports\rei_model_ab_sequence_all13_64k_gpu999_fixed3\sequence_plan.json`
- **summary:** `output\reports\rei_model_ab_sequence_all13_64k_gpu999_fixed3\sequence_summary.json`
- **report:** `output\reports\rei_model_ab_sequence_all13_64k_gpu999_fixed3\sequence_report.md`
- **progress:** `output\reports\rei_model_ab_sequence_all13_64k_gpu999_fixed3\sequence_progress.log`
- **synthesis_jsonl:** `output\reports\rei_model_ab_sequence_all13_64k_gpu999_fixed3\sequence_synthesis.jsonl`
- **synthesis_report:** `output\reports\rei_model_ab_sequence_all13_64k_gpu999_fixed3\sequence_synthesis_report.md`