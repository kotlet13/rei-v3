# REI Profile Matrix Evaluation Summary

Run: `20260517_170409`

Raw artifacts live under `output/reports/rei_profile_matrix/20260517_170409_granite4_1_30b_64k_gpu999/` and are intentionally not committed.

## Configuration

- Provider: `ollama`
- Model: `granite4.1:30b`
- Context: `65536`
- GPU layers: `999`
- Profiles: `13`
- Scenarios: `12`
- Cases: `156`
- Total live tokens: `1,505,164`

## Runtime Health

- Fallback count: `0`
- Final required-key failures: `0`
- Raw LLM required-key failures: `0`
- Processor identity violations: `0`
- Processor distinctness threshold failures: `0`
- Max processor overlap: `0.2062`
- Average processor overlap: `0.0989`

Note: the generated raw `summary.json` reports `missing_required_key_case_count=156`, but inspection of `cases.json` shows every final and raw-call missing-key list is empty. The count is an evaluator aggregation bug: it treated the presence of raw-call rows as missing keys even when each row had `missing: []`.

## Profile Sensitivity

Every scenario produced `13/13` unique Ego signatures across the 13 profiles. No scenario collapsed to identical EgoResultant behavior across all profiles.

| Scenario | Unique Ego signatures | Identical across profiles |
|---|---:|---|
| `meeting_avoidance` | `13/13` | `false` |
| `quit_job_start_business` | `13/13` | `false` |
| `public_speaking_freeze` | `13/13` | `false` |
| `romantic_return_loop` | `13/13` | `false` |
| `conflict_with_coworker` | `13/13` | `false` |
| `risky_opportunity` | `13/13` | `false` |
| `expensive_purchase` | `13/13` | `false` |
| `grief_loss` | `13/13` | `false` |
| `creative_project_obsession` | `13/13` | `false` |
| `boundary_violation` | `13/13` | `false` |
| `moral_dilemma` | `13/13` | `false` |
| `family_attachment_decision` | `13/13` | `false` |

## R=E=I Check

`R=E=I` did not globally default to Racio. It did produce Racio as resultant/leading in these two scenarios:

- `quit_job_start_business`
- `conflict_with_coworker`

This should be reviewed as scenario-specific behavior rather than a global Racio-default failure.

## True-Positive Checks

| Check | Result |
|---|---:|
| `public_speaking_freeze` body/freeze pressure | `13/13` detected |
| `boundary_violation` boundary/protection pressure | `10/13` detected |
| `quit_job_start_business` Racio delay + Emocio freedom + Instinkt stability | `12/13` detected |
| `romantic_return_loop` relationship return / attachment loop | `2/13` detected |

The main behavioral gap remains romantic return-loop recall: false positives are under control, but the stricter detector misses most true romantic-return cases.

## False Positives

False-positive case count: `1`

- `creative_project_obsession::R>E>I`
  - Flag: `boundary_pressure_on_unexpected_scenario`
  - Interpretation: likely a borderline/evaluator issue, because the scenario explicitly mentions health, money, and relationships needing attention, so Instinkt boundary/protection language is plausible.

## False Negatives

False-negative case count: `70`

Breakdown:

| Scenario | False negatives | Passing cases |
|---|---:|---:|
| `meeting_avoidance` | `13` | `0` |
| `quit_job_start_business` | `1` | `12` |
| `public_speaking_freeze` | `0` | `13` |
| `romantic_return_loop` | `11` | `2` |
| `conflict_with_coworker` | `0` | `13` |
| `risky_opportunity` | `13` | `0` |
| `expensive_purchase` | `1` | `12` |
| `grief_loss` | `0` | `13` |
| `creative_project_obsession` | `13` | `0` |
| `boundary_violation` | `3` | `10` |
| `moral_dilemma` | `13` | `0` |
| `family_attachment_decision` | `2` | `11` |

Several false-negative groups appear to be evaluator-threshold issues, especially `meeting_avoidance`, `risky_opportunity`, `creative_project_obsession`, and `moral_dilemma`, where the model output was structurally valid and profile-sensitive but did not hit the exact expected pattern heuristic.

## Overall Read

The run is technically healthy: no fallbacks, no schema misses, no processor identity corruption, and strong profile sensitivity. The next useful patch is not a broad runtime rewrite. It is a targeted evaluator/acceptance calibration pass:

- Fix the missing-key aggregation bug in the profile matrix script.
- Improve romantic return-loop true-positive detection without reopening meeting/business false positives.
- Revisit overly literal expected-pattern heuristics for rationalization, risk, moral dilemma, and creative obsession scenarios.
