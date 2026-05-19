# REI Profile Matrix Evaluation

- Run id: `20260519_153731`
- Provider: `ollama`
- Model: `granite4.1:30b`
- Context: `65536`
- GPU layers: `999`
- Cases: `156`
- Fallback count: `0`
- Missing-key case count: `0`
- Processor identity violations: `0`
- False-positive case count: `1`
- False-negative case count: `9`
- Hard false-negative case count: `8`
- Soft false-negative case count: `1`
- Actionable failure case count: `9`
- Evaluator-warning case count: `66`
- Total tokens: `1501216`

## Old vs New Metrics

| Metric | Previous run | Current run |
|---|---:|---:|
| `fallback_count` | `0` | `0` |
| `true_missing_required_key_count` | `0` | `0` |
| `hard_false_negative_count` | `not split` | `8` |
| `soft_false_negative_count` | `not split` | `1` |
| `actionable_failure_count` | `not split` | `9` |
| `false_positive_count` | `1` | `1` |
| `rei_racio_default_case_count` | `2` | `1` |
| `processor_identity_violation_count` | `0` | `0` |

## Profile Sensitivity

| Scenario | Cases | Unique Ego signatures | Identical across profiles | Profile leaders | Situational drivers | Resultants | Action classes | Semantic diversity flags |
|---|---:|---:|---|---|---|---|---|---|
| `boundary_violation` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 7, 'unknown': 6}` | `{'emocio': 2, 'instinkt': 8, 'mixed': 3}` | `{'delay_analyze': 1, 'protect_boundary': 5, 'withdraw_freeze': 7}` | `[]` |
| `conflict_with_coworker` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'emocio': 2, 'instinkt': 7, 'mixed': 3, 'unknown': 1}` | `{'emocio': 3, 'instinkt': 3, 'mixed': 5, 'racio': 2}` | `{'approach_confront': 5, 'delay_analyze': 1, 'withdraw_freeze': 7}` | `[]` |
| `creative_project_obsession` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 12, 'unknown': 1}` | `{'emocio': 4, 'instinkt': 7, 'mixed': 2}` | `{'delay_analyze': 8, 'withdraw_freeze': 5}` | `[]` |
| `expensive_purchase` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 4, 'mixed': 2, 'unknown': 7}` | `{'emocio': 2, 'instinkt': 8, 'mixed': 3}` | `{'delay_analyze': 13}` | `[]` |
| `family_attachment_decision` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'emocio': 1, 'instinkt': 6, 'mixed': 2, 'unknown': 4}` | `{'emocio': 2, 'instinkt': 5, 'mixed': 4, 'racio': 2}` | `{'approach_confront': 1, 'delay_analyze': 2, 'protect_boundary': 5, 'pursue_commit': 1, 'withdraw_freeze': 4}` | `[]` |
| `grief_loss` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 13}` | `{'emocio': 3, 'instinkt': 10}` | `{'delay_analyze': 8, 'withdraw_freeze': 5}` | `[]` |
| `meeting_avoidance` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 9, 'unknown': 4}` | `{'emocio': 5, 'instinkt': 6, 'mixed': 1, 'racio': 1}` | `{'approach_confront': 8, 'delay_analyze': 1, 'mixed_or_unclear': 1, 'withdraw_freeze': 3}` | `[]` |
| `moral_dilemma` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 10, 'unknown': 3}` | `{'emocio': 5, 'instinkt': 5, 'mixed': 3}` | `{'ethical_disclosure': 12, 'withdraw_freeze': 1}` | `[]` |
| `public_speaking_freeze` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 9, 'mixed': 1, 'unknown': 3}` | `{'emocio': 3, 'instinkt': 7, 'mixed': 3}` | `{'delay_analyze': 5, 'withdraw_freeze': 8}` | `[]` |
| `quit_job_start_business` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'emocio': 1, 'instinkt': 4, 'mixed': 8}` | `{'emocio': 2, 'instinkt': 3, 'mixed': 6, 'racio': 2}` | `{'delay_analyze': 13}` | `[]` |
| `risky_opportunity` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 9, 'unknown': 4}` | `{'emocio': 1, 'instinkt': 11, 'mixed': 1}` | `{'mixed_or_unclear': 1, 'pursue_commit': 2, 'withdraw_freeze': 10}` | `[]` |
| `romantic_return_loop` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'emocio': 1, 'instinkt': 7, 'mixed': 4, 'unknown': 1}` | `{'emocio': 3, 'instinkt': 6, 'mixed': 3, 'racio': 1}` | `{'relationship_return': 13}` | `[]` |

## Quality Flags

- False positives: `['grief_loss::REI']`
- False negatives: `['romantic_return_loop::R>I>E', 'boundary_violation::E>R>I', 'boundary_violation::REI', 'family_attachment_decision::I', 'family_attachment_decision::EI', 'family_attachment_decision::R>E>I', 'family_attachment_decision::I>R>E', 'family_attachment_decision::I>E>R', 'family_attachment_decision::REI']`
- Actionable failures: `['romantic_return_loop::R>I>E', 'boundary_violation::E>R>I', 'boundary_violation::REI', 'family_attachment_decision::I', 'family_attachment_decision::EI', 'family_attachment_decision::R>E>I', 'family_attachment_decision::I>R>E', 'family_attachment_decision::I>E>R', 'family_attachment_decision::REI']`
- Hard false negatives: `['boundary_violation::E>R>I', 'boundary_violation::REI', 'family_attachment_decision::I', 'family_attachment_decision::EI', 'family_attachment_decision::R>E>I', 'family_attachment_decision::I>R>E', 'family_attachment_decision::I>E>R', 'family_attachment_decision::REI']`
- Soft false negatives: `['romantic_return_loop::R>I>E']`
- Evaluator warnings: `['meeting_avoidance::R', 'meeting_avoidance::E', 'meeting_avoidance::I', 'meeting_avoidance::RE', 'meeting_avoidance::RI', 'meeting_avoidance::EI', 'meeting_avoidance::R>E>I', 'meeting_avoidance::R>I>E', 'meeting_avoidance::E>R>I', 'meeting_avoidance::E>I>R', 'meeting_avoidance::I>R>E', 'meeting_avoidance::I>E>R', 'meeting_avoidance::REI', 'romantic_return_loop::R', 'romantic_return_loop::E', 'romantic_return_loop::I', 'romantic_return_loop::RE', 'romantic_return_loop::RI', 'romantic_return_loop::EI', 'romantic_return_loop::R>E>I', 'romantic_return_loop::E>R>I', 'romantic_return_loop::E>I>R', 'romantic_return_loop::I>R>E', 'romantic_return_loop::I>E>R', 'romantic_return_loop::REI', 'risky_opportunity::R', 'risky_opportunity::E', 'risky_opportunity::I', 'risky_opportunity::RE', 'risky_opportunity::RI', 'risky_opportunity::EI', 'risky_opportunity::R>E>I', 'risky_opportunity::R>I>E', 'risky_opportunity::E>R>I', 'risky_opportunity::E>I>R', 'risky_opportunity::I>R>E', 'risky_opportunity::I>E>R', 'risky_opportunity::REI', 'creative_project_obsession::R', 'creative_project_obsession::E', 'creative_project_obsession::I', 'creative_project_obsession::RE', 'creative_project_obsession::RI', 'creative_project_obsession::EI', 'creative_project_obsession::R>E>I', 'creative_project_obsession::R>I>E', 'creative_project_obsession::E>R>I', 'creative_project_obsession::E>I>R', 'creative_project_obsession::I>R>E', 'creative_project_obsession::I>E>R', 'creative_project_obsession::REI', 'boundary_violation::E>R>I', 'boundary_violation::REI', 'moral_dilemma::R', 'moral_dilemma::E', 'moral_dilemma::I', 'moral_dilemma::RE', 'moral_dilemma::RI', 'moral_dilemma::EI', 'moral_dilemma::R>E>I', 'moral_dilemma::R>I>E', 'moral_dilemma::E>R>I', 'moral_dilemma::E>I>R', 'moral_dilemma::I>R>E', 'moral_dilemma::I>E>R', 'moral_dilemma::REI']`
- Missing required keys: `[]`
- Processor identity violations: `[]`
- R=E=I Racio-default cases: `['quit_job_start_business']`

## Case Table

| Scenario | Profile | Fallbacks | Tokens | Max Jaccard | Profile leader | Situational driver | Resultant | Leading | Action class | False positives | False negatives | Severity |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|
| `meeting_avoidance` | `R` | `0` | `9212` | `0.0667` | `racio` | `unknown` | `racio` | `racio` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `E` | `0` | `9052` | `0.0708` | `emocio` | `unknown` | `emocio` | `emocio` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `I` | `0` | `9655` | `0.0971` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `RE` | `0` | `9214` | `0.0698` | `mixed` | `instinkt` | `mixed` | `mixed` | `mixed_or_unclear` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `RI` | `0` | `9095` | `0.0899` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `EI` | `0` | `9379` | `0.0926` | `mixed` | `unknown` | `instinkt` | `instinkt` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `R>E>I` | `0` | `9175` | `0.0941` | `racio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `R>I>E` | `0` | `9429` | `0.0619` | `racio` | `instinkt` | `instinkt` | `instinkt` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `E>R>I` | `0` | `9332` | `0.134` | `emocio` | `unknown` | `emocio` | `emocio` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `E>I>R` | `0` | `9275` | `0.1158` | `emocio` | `instinkt` | `emocio` | `emocio` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `I>R>E` | `0` | `9557` | `0.053` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `I>E>R` | `0` | `9555` | `0.0935` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `REI` | `0` | `9547` | `0.0685` | `tie` | `instinkt` | `emocio` | `emocio` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `quit_job_start_business` | `R` | `0` | `9935` | `0.1006` | `racio` | `mixed` | `racio` | `racio` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `E` | `0` | `9801` | `0.0816` | `emocio` | `mixed` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I` | `0` | `10220` | `0.0789` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `RE` | `0` | `9919` | `0.076` | `mixed` | `instinkt` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `RI` | `0` | `10018` | `0.0769` | `mixed` | `emocio` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `EI` | `0` | `9945` | `0.0875` | `mixed` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `R>E>I` | `0` | `9886` | `0.0732` | `racio` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `R>I>E` | `0` | `10044` | `0.1091` | `racio` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `E>R>I` | `0` | `9886` | `0.0602` | `emocio` | `mixed` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `E>I>R` | `0` | `9799` | `0.0942` | `emocio` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I>R>E` | `0` | `10057` | `0.0637` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I>E>R` | `0` | `10172` | `0.0625` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `REI` | `0` | `9953` | `0.0732` | `tie` | `mixed` | `racio` | `racio` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `R` | `0` | `9501` | `0.0606` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `E` | `0` | `9606` | `0.0657` | `emocio` | `instinkt` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `I` | `0` | `9647` | `0.0488` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `RE` | `0` | `9484` | `0.0571` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `RI` | `0` | `9545` | `0.0611` | `mixed` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `EI` | `0` | `9362` | `0.0815` | `mixed` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `R>E>I` | `0` | `9762` | `0.0522` | `racio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `R>I>E` | `0` | `9476` | `0.0865` | `racio` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `E>R>I` | `0` | `9320` | `0.0877` | `emocio` | `unknown` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `E>I>R` | `0` | `9506` | `0.1111` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `I>R>E` | `0` | `9503` | `0.0821` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `I>E>R` | `0` | `9449` | `0.0598` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `REI` | `0` | `9663` | `0.0519` | `tie` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `romantic_return_loop` | `R` | `0` | `9679` | `0.1463` | `racio` | `unknown` | `racio` | `racio` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `E` | `0` | `9498` | `0.1061` | `emocio` | `instinkt` | `emocio` | `emocio` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `I` | `0` | `9654` | `0.0882` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `RE` | `0` | `9781` | `0.1471` | `mixed` | `instinkt` | `mixed` | `mixed` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `RI` | `0` | `9731` | `0.1377` | `mixed` | `mixed` | `mixed` | `mixed` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `EI` | `0` | `9834` | `0.0909` | `mixed` | `mixed` | `mixed` | `mixed` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `R>E>I` | `0` | `9750` | `0.0966` | `racio` | `mixed` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `R>I>E` | `0` | `9625` | `0.1387` | `racio` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | soft_false_negative:1 |
| `romantic_return_loop` | `E>R>I` | `0` | `9514` | `0.0977` | `emocio` | `emocio` | `emocio` | `emocio` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `E>I>R` | `0` | `9488` | `0.0992` | `emocio` | `instinkt` | `emocio` | `emocio` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `I>R>E` | `0` | `9912` | `0.1192` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `I>E>R` | `0` | `9621` | `0.0658` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `REI` | `0` | `9680` | `0.1061` | `tie` | `mixed` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `conflict_with_coworker` | `R` | `0` | `9336` | `0.0978` | `racio` | `mixed` | `racio` | `racio` | `approach_confront` | none | none | none |
| `conflict_with_coworker` | `E` | `0` | `9379` | `0.0971` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `I` | `0` | `9502` | `0.0885` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `RE` | `0` | `9417` | `0.0833` | `mixed` | `instinkt` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `RI` | `0` | `9438` | `0.0833` | `mixed` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `EI` | `0` | `9363` | `0.0842` | `mixed` | `unknown` | `mixed` | `mixed` | `approach_confront` | none | none | none |
| `conflict_with_coworker` | `R>E>I` | `0` | `9363` | `0.0719` | `racio` | `emocio` | `mixed` | `mixed` | `approach_confront` | none | none | none |
| `conflict_with_coworker` | `R>I>E` | `0` | `9200` | `0.1099` | `racio` | `instinkt` | `racio` | `racio` | `approach_confront` | none | none | none |
| `conflict_with_coworker` | `E>R>I` | `0` | `9394` | `0.0865` | `emocio` | `emocio` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `E>I>R` | `0` | `9377` | `0.1078` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `I>R>E` | `0` | `9362` | `0.0792` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `conflict_with_coworker` | `I>E>R` | `0` | `9454` | `0.0755` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `approach_confront` | none | none | none |
| `conflict_with_coworker` | `REI` | `0` | `9288` | `0.1026` | `tie` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `risky_opportunity` | `R` | `0` | `9605` | `0.0876` | `racio` | `unknown` | `instinkt` | `instinkt` | `pursue_commit` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `E` | `0` | `9416` | `0.1238` | `emocio` | `instinkt` | `mixed` | `mixed` | `mixed_or_unclear` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `I` | `0` | `9310` | `0.1263` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `RE` | `0` | `9371` | `0.0745` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `RI` | `0` | `9400` | `0.0544` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `EI` | `0` | `9341` | `0.1019` | `mixed` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `R>E>I` | `0` | `9236` | `0.1224` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `R>I>E` | `0` | `9180` | `0.0885` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `E>R>I` | `0` | `9362` | `0.0769` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `E>I>R` | `0` | `9342` | `0.1031` | `emocio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `I>R>E` | `0` | `9537` | `0.0815` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `I>E>R` | `0` | `9426` | `0.1053` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `REI` | `0` | `9454` | `0.0941` | `tie` | `unknown` | `instinkt` | `instinkt` | `pursue_commit` | none | rationalization_missing | evaluator_warning:1 |
| `expensive_purchase` | `R` | `0` | `9473` | `0.0821` | `racio` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `E` | `0` | `9276` | `0.0775` | `emocio` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `I` | `0` | `9126` | `0.0551` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `RE` | `0` | `9405` | `0.0865` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `RI` | `0` | `9160` | `0.098` | `mixed` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `EI` | `0` | `9255` | `0.0602` | `mixed` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `R>E>I` | `0` | `9533` | `0.0777` | `racio` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `R>I>E` | `0` | `9526` | `0.0583` | `racio` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `E>R>I` | `0` | `9425` | `0.0752` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `E>I>R` | `0` | `9730` | `0.0822` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `I>R>E` | `0` | `9453` | `0.0719` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `I>E>R` | `0` | `9400` | `0.0651` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `REI` | `0` | `9559` | `0.0508` | `tie` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `R` | `0` | `10402` | `0.1176` | `racio` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `E` | `0` | `10318` | `0.1525` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `I` | `0` | `9934` | `0.1243` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `RE` | `0` | `9829` | `0.1384` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `RI` | `0` | `9992` | `0.1078` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `EI` | `0` | `10150` | `0.0995` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `R>E>I` | `0` | `10016` | `0.1096` | `racio` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `R>I>E` | `0` | `10159` | `0.1` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `E>R>I` | `0` | `9823` | `0.128` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `grief_loss` | `E>I>R` | `0` | `10130` | `0.126` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `grief_loss` | `I>R>E` | `0` | `10148` | `0.15` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `I>E>R` | `0` | `9990` | `0.1301` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `REI` | `0` | `10176` | `0.0727` | `tie` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | boundary_pressure_on_unexpected_scenario | none | none |
| `creative_project_obsession` | `R` | `0` | `10312` | `0.1118` | `racio` | `instinkt` | `mixed` | `mixed` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `E` | `0` | `9853` | `0.0833` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `I` | `0` | `9945` | `0.0888` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `RE` | `0` | `10066` | `0.1288` | `mixed` | `instinkt` | `mixed` | `mixed` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `RI` | `0` | `9638` | `0.1203` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `EI` | `0` | `10145` | `0.1218` | `mixed` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `R>E>I` | `0` | `10008` | `0.1034` | `racio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `R>I>E` | `0` | `9767` | `0.1118` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `E>R>I` | `0` | `9927` | `0.0795` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `E>I>R` | `0` | `9754` | `0.1135` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `I>R>E` | `0` | `10002` | `0.1143` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `I>E>R` | `0` | `9826` | `0.0952` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `REI` | `0` | `9811` | `0.1` | `tie` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `boundary_violation` | `R` | `0` | `9559` | `0.1032` | `racio` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `E` | `0` | `9373` | `0.163` | `emocio` | `unknown` | `mixed` | `mixed` | `protect_boundary` | none | none | none |
| `boundary_violation` | `I` | `0` | `9633` | `0.1059` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `boundary_violation` | `RE` | `0` | `9433` | `0.1` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `RI` | `0` | `9313` | `0.0608` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `EI` | `0` | `9524` | `0.1034` | `mixed` | `unknown` | `mixed` | `mixed` | `protect_boundary` | none | none | none |
| `boundary_violation` | `R>E>I` | `0` | `9413` | `0.0968` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `R>I>E` | `0` | `9403` | `0.1228` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `E>R>I` | `0` | `9314` | `0.0992` | `emocio` | `instinkt` | `emocio` | `emocio` | `protect_boundary` | none | expected_patterns_missing,boundary_pressure_missing | hard_false_negative:1,evaluator_warning:1 |
| `boundary_violation` | `E>I>R` | `0` | `9383` | `0.114` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `I>R>E` | `0` | `9616` | `0.1325` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `boundary_violation` | `I>E>R` | `0` | `9355` | `0.1284` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `REI` | `0` | `9622` | `0.1182` | `tie` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | expected_patterns_missing,boundary_pressure_missing | hard_false_negative:1,evaluator_warning:1 |
| `moral_dilemma` | `R` | `0` | `9713` | `0.1` | `racio` | `instinkt` | `mixed` | `mixed` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `E` | `0` | `9550` | `0.1223` | `emocio` | `unknown` | `emocio` | `emocio` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `I` | `0` | `9705` | `0.1271` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `RE` | `0` | `9585` | `0.0744` | `mixed` | `instinkt` | `mixed` | `mixed` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `RI` | `0` | `9546` | `0.0973` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `EI` | `0` | `9557` | `0.1523` | `mixed` | `unknown` | `instinkt` | `instinkt` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `R>E>I` | `0` | `9647` | `0.1171` | `racio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `R>I>E` | `0` | `9923` | `0.1163` | `racio` | `instinkt` | `mixed` | `mixed` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `E>R>I` | `0` | `9793` | `0.0972` | `emocio` | `unknown` | `emocio` | `emocio` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `E>I>R` | `0` | `9602` | `0.0949` | `emocio` | `instinkt` | `emocio` | `emocio` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `I>R>E` | `0` | `9596` | `0.1221` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `I>E>R` | `0` | `9840` | `0.1027` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `REI` | `0` | `9795` | `0.1161` | `tie` | `instinkt` | `emocio` | `emocio` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `family_attachment_decision` | `R` | `0` | `9539` | `0.1695` | `racio` | `unknown` | `racio` | `racio` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `E` | `0` | `9663` | `0.1217` | `emocio` | `unknown` | `mixed` | `mixed` | `approach_confront` | none | none | none |
| `family_attachment_decision` | `I` | `0` | `9726` | `0.1712` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | boundary_pressure_missing | hard_false_negative:1 |
| `family_attachment_decision` | `RE` | `0` | `9520` | `0.1364` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `RI` | `0` | `9444` | `0.1525` | `mixed` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `family_attachment_decision` | `EI` | `0` | `9508` | `0.1176` | `mixed` | `unknown` | `mixed` | `mixed` | `protect_boundary` | none | boundary_pressure_missing | hard_false_negative:1 |
| `family_attachment_decision` | `R>E>I` | `0` | `9550` | `0.1376` | `racio` | `emocio` | `racio` | `racio` | `pursue_commit` | none | boundary_pressure_missing | hard_false_negative:1 |
| `family_attachment_decision` | `R>I>E` | `0` | `9887` | `0.1371` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `E>R>I` | `0` | `9941` | `0.0821` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `E>I>R` | `0` | `9683` | `0.1593` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `I>R>E` | `0` | `9646` | `0.1635` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `protect_boundary` | none | boundary_pressure_missing | hard_false_negative:1 |
| `family_attachment_decision` | `I>E>R` | `0` | `9747` | `0.1121` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `protect_boundary` | none | boundary_pressure_missing | hard_false_negative:1 |
| `family_attachment_decision` | `REI` | `0` | `9571` | `0.1217` | `tie` | `mixed` | `mixed` | `mixed` | `protect_boundary` | none | boundary_pressure_missing | hard_false_negative:1 |