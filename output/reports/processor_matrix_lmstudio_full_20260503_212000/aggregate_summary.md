# Processor Matrix Aggregate Summary

## Global Metrics

- **run_id:** `20260503_211923`
- **provider:** `lmstudio`
- **model:** `qwen/qwen3.5-9b`
- **total_calls:** `18`
- **fallback_rate:** `0.0`
- **valid_json_rate:** `1.0`
- **average_schema_score:** `1.0`
- **average_role_score:** `0.86`
- **average_distinctness_score:** `1.0`
- **average_overall_score:** `0.958`
- **distinctness_pass_rate:** `1.0`

## Violations

- **style_violations:** none
- **rei_violations:** none

## Per Mind

### emocio

- **total_calls:** `6`
- **fallback_rate:** `0.0`
- **valid_json_rate:** `1.0`
- **average_schema_score:** `1.0`
- **average_role_score:** `0.92`
- **average_distinctness_score:** `1.0`
- **average_overall_score:** `0.976`

### instinkt

- **total_calls:** `6`
- **fallback_rate:** `0.0`
- **valid_json_rate:** `1.0`
- **average_schema_score:** `1.0`
- **average_role_score:** `0.9`
- **average_distinctness_score:** `1.0`
- **average_overall_score:** `0.97`

### racio

- **total_calls:** `6`
- **fallback_rate:** `0.0`
- **valid_json_rate:** `1.0`
- **average_schema_score:** `1.0`
- **average_role_score:** `0.76`
- **average_distinctness_score:** `1.0`
- **average_overall_score:** `0.928`

## Per Model

### qwen/qwen3.5-9b

- **total_calls:** `18`
- **fallback_rate:** `0.0`
- **valid_json_rate:** `1.0`
- **average_overall_score:** `0.958`

## Distinctness

- `business-runway` repeat `1` max_overlap=`0.1163` pass=`True`
- `career-family` repeat `1` max_overlap=`0.0938` pass=`True`
- `creative-exposure` repeat `1` max_overlap=`0.0964` pass=`True`
- `lifestyle-choice` repeat `1` max_overlap=`0.0861` pass=`True`
- `public-stage` repeat `1` max_overlap=`0.0583` pass=`True`
- `relationship-boundary` repeat `1` max_overlap=`0.1159` pass=`True`

## Output Files

- **summary:** `output/reports/processor_matrix_lmstudio_full_20260503_212000/summary.json`
- **results_jsonl:** `output/reports/processor_matrix_lmstudio_full_20260503_212000/results.jsonl`
- **aggregate_markdown:** `output/reports/processor_matrix_lmstudio_full_20260503_212000/aggregate_summary.md`
- **aggregate_json:** `output/reports/processor_matrix_lmstudio_full_20260503_212000/aggregate_summary.json`
- **progress:** `output/reports/processor_matrix_lmstudio_full_20260503_212000/progress.log`