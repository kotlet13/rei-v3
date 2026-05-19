# REI Profile Matrix Evaluation

- Run id: `20260519_191850`
- Provider: `ollama`
- Model: `granite4.1:30b`
- Context: `65536`
- GPU layers: `999`
- Cases: `40`
- Fallback count: `0`
- Missing-key case count: `0`
- Processor identity violations: `0`
- False-positive case count: `0`
- False-negative case count: `0`
- Hard false-negative case count: `0`
- Soft false-negative case count: `0`
- Actionable failure case count: `0`
- Evaluator-warning case count: `0`
- Total tokens: `389386`

## Old vs New Metrics

| Metric | Previous run | Current run |
|---|---:|---:|
| `fallback_count` | `0` | `0` |
| `true_missing_required_key_count` | `0` | `0` |
| `hard_false_negative_count` | `not split` | `0` |
| `soft_false_negative_count` | `not split` | `0` |
| `actionable_failure_count` | `not split` | `0` |
| `false_positive_count` | `1` | `0` |
| `rei_racio_default_case_count` | `2` | `1` |
| `processor_identity_violation_count` | `0` | `0` |

## Profile Sensitivity

| Scenario | Cases | Unique Ego signatures | Identical across profiles | Profile leaders | Situational drivers | Resultants | Action classes | Semantic diversity flags |
|---|---:|---:|---|---|---|---|---|---|
| `boundary_violation` | `8` | `8` | `False` | `{'emocio': 1, 'instinkt': 3, 'mixed': 1, 'racio': 2, 'tie': 1}` | `{'instinkt': 2, 'unknown': 6}` | `{'emocio': 2, 'instinkt': 5, 'mixed': 1}` | `{'protect_boundary': 4, 'withdraw_freeze': 4}` | `[]` |
| `family_attachment_decision` | `8` | `8` | `False` | `{'emocio': 1, 'instinkt': 3, 'mixed': 1, 'racio': 2, 'tie': 1}` | `{'instinkt': 6, 'unknown': 2}` | `{'emocio': 2, 'instinkt': 6}` | `{'delay_analyze': 3, 'protect_boundary': 3, 'withdraw_freeze': 2}` | `[]` |
| `grief_loss` | `8` | `8` | `False` | `{'emocio': 1, 'instinkt': 3, 'mixed': 1, 'racio': 2, 'tie': 1}` | `{'instinkt': 7, 'unknown': 1}` | `{'emocio': 1, 'instinkt': 6, 'racio': 1}` | `{'delay_analyze': 3, 'protect_boundary': 1, 'withdraw_freeze': 4}` | `[]` |
| `quit_job_start_business` | `8` | `8` | `False` | `{'emocio': 1, 'instinkt': 3, 'mixed': 1, 'racio': 2, 'tie': 1}` | `{'emocio': 1, 'instinkt': 5, 'mixed': 2}` | `{'emocio': 1, 'instinkt': 5, 'racio': 2}` | `{'delay_analyze': 8}` | `[]` |
| `romantic_return_loop` | `8` | `8` | `False` | `{'emocio': 1, 'instinkt': 3, 'mixed': 1, 'racio': 2, 'tie': 1}` | `{'emocio': 1, 'instinkt': 5, 'mixed': 2}` | `{'emocio': 1, 'instinkt': 6, 'mixed': 1}` | `{'relationship_return': 8}` | `[]` |

## Quality Flags

- False positives: `[]`
- False negatives: `[]`
- Actionable failures: `[]`
- Hard false negatives: `[]`
- Soft false negatives: `[]`
- Evaluator warnings: `[]`
- Missing required keys: `[]`
- Processor identity violations: `[]`
- R=E=I Racio-default cases: `['quit_job_start_business']`

## Case Table

| Scenario | Profile | Fallbacks | Tokens | Max Jaccard | Profile leader | Situational driver | Resultant | Leading | Action class | False positives | False negatives | Severity |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|
| `quit_job_start_business` | `REI` | `0` | `10338` | `0.061` | `tie` | `mixed` | `racio` | `racio` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `E>R>I` | `0` | `9708` | `0.0621` | `emocio` | `mixed` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `R>I>E` | `0` | `9931` | `0.1067` | `racio` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I` | `0` | `9918` | `0.0994` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `EI` | `0` | `9899` | `0.087` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `R>E>I` | `0` | `9859` | `0.0875` | `racio` | `emocio` | `racio` | `racio` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I>R>E` | `0` | `10220` | `0.0686` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I>E>R` | `0` | `10006` | `0.0682` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `romantic_return_loop` | `REI` | `0` | `9857` | `0.0909` | `tie` | `mixed` | `mixed` | `mixed` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `E>R>I` | `0` | `9748` | `0.0927` | `emocio` | `mixed` | `emocio` | `emocio` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `R>I>E` | `0` | `9721` | `0.0743` | `racio` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `I` | `0` | `9616` | `0.0952` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `EI` | `0` | `9700` | `0.1145` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `R>E>I` | `0` | `9494` | `0.0853` | `racio` | `emocio` | `instinkt` | `instinkt` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `I>R>E` | `0` | `9542` | `0.124` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `I>E>R` | `0` | `9591` | `0.096` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | none | none |
| `grief_loss` | `REI` | `0` | `9934` | `0.1296` | `tie` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `E>R>I` | `0` | `9997` | `0.1026` | `emocio` | `instinkt` | `emocio` | `emocio` | `protect_boundary` | none | none | none |
| `grief_loss` | `R>I>E` | `0` | `10053` | `0.1231` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `I` | `0` | `10165` | `0.1329` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `EI` | `0` | `9871` | `0.0915` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `R>E>I` | `0` | `10124` | `0.1459` | `racio` | `instinkt` | `racio` | `racio` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `I>R>E` | `0` | `9981` | `0.163` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `I>E>R` | `0` | `9846` | `0.1558` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `boundary_violation` | `REI` | `0` | `9630` | `0.087` | `tie` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `E>R>I` | `0` | `9519` | `0.0973` | `emocio` | `unknown` | `emocio` | `emocio` | `protect_boundary` | none | none | none |
| `boundary_violation` | `R>I>E` | `0` | `9427` | `0.0962` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `I` | `0` | `9250` | `0.0965` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `EI` | `0` | `9587` | `0.0947` | `mixed` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `R>E>I` | `0` | `9218` | `0.0745` | `racio` | `unknown` | `emocio` | `emocio` | `protect_boundary` | none | none | none |
| `boundary_violation` | `I>R>E` | `0` | `9303` | `0.0813` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `boundary_violation` | `I>E>R` | `0` | `9359` | `0.0833` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `REI` | `0` | `9883` | `0.1351` | `tie` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `E>R>I` | `0` | `9669` | `0.1667` | `emocio` | `unknown` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `family_attachment_decision` | `R>I>E` | `0` | `9590` | `0.0909` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `I` | `0` | `9555` | `0.1349` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `family_attachment_decision` | `EI` | `0` | `9581` | `0.1379` | `mixed` | `unknown` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `R>E>I` | `0` | `9692` | `0.1417` | `racio` | `instinkt` | `emocio` | `emocio` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `I>R>E` | `0` | `9390` | `0.1604` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `I>E>R` | `0` | `9614` | `0.1145` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |