# REI Profile Matrix Evaluation

- Run id: `20260518_222328`
- Provider: `ollama`
- Model: `granite4.1:30b`
- Context: `65536`
- GPU layers: `999`
- Cases: `156`
- Fallback count: `1`
- Missing-key case count: `0`
- Processor identity violations: `0`
- False-positive case count: `1`
- False-negative case count: `7`
- Hard false-negative case count: `6`
- Soft false-negative case count: `1`
- Actionable failure case count: `7`
- Evaluator-warning case count: `65`
- Total tokens: `1495882`

## Old vs New Metrics

| Metric | Previous run | Current run |
|---|---:|---:|
| `fallback_count` | `0` | `1` |
| `true_missing_required_key_count` | `0` | `0` |
| `hard_false_negative_count` | `not split` | `6` |
| `soft_false_negative_count` | `not split` | `1` |
| `actionable_failure_count` | `not split` | `7` |
| `false_positive_count` | `1` | `1` |
| `rei_racio_default_case_count` | `2` | `1` |
| `processor_identity_violation_count` | `0` | `0` |

## Profile Sensitivity

| Scenario | Cases | Unique Ego signatures | Identical across profiles | Profile leaders | Situational drivers | Resultants | Action classes | Semantic diversity flags |
|---|---:|---:|---|---|---|---|---|---|
| `boundary_violation` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 8, 'unknown': 5}` | `{'emocio': 3, 'instinkt': 7, 'mixed': 2, 'racio': 1}` | `{'protect_boundary': 6, 'withdraw_freeze': 7}` | `[]` |
| `conflict_with_coworker` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'emocio': 2, 'instinkt': 8, 'mixed': 3}` | `{'emocio': 3, 'instinkt': 4, 'mixed': 3, 'racio': 3}` | `{'approach_confront': 4, 'withdraw_freeze': 9}` | `[]` |
| `creative_project_obsession` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 2, 'racio': 3, 'tie': 1, 'unknown': 1}` | `{'instinkt': 13}` | `{'emocio': 1, 'instinkt': 11, 'mixed': 1}` | `{'delay_analyze': 11, 'withdraw_freeze': 2}` | `[]` |
| `expensive_purchase` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'unknown': 1}` | `{'instinkt': 6, 'mixed': 2, 'unknown': 5}` | `{'emocio': 3, 'instinkt': 7, 'mixed': 2, 'racio': 1}` | `{'delay_analyze': 13}` | `[]` |
| `family_attachment_decision` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'unknown': 1}` | `{'emocio': 1, 'instinkt': 9, 'unknown': 3}` | `{'emocio': 3, 'instinkt': 8, 'mixed': 1, 'racio': 1}` | `{'approach_confront': 1, 'protect_boundary': 5, 'withdraw_freeze': 7}` | `[]` |
| `grief_loss` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'unknown': 1}` | `{'instinkt': 12, 'unknown': 1}` | `{'emocio': 3, 'instinkt': 10}` | `{'delay_analyze': 4, 'withdraw_freeze': 9}` | `[]` |
| `meeting_avoidance` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'unknown': 1}` | `{'instinkt': 7, 'mixed': 1, 'unknown': 5}` | `{'emocio': 4, 'instinkt': 4, 'mixed': 3, 'racio': 2}` | `{'approach_confront': 5, 'delay_analyze': 2, 'mixed_or_unclear': 3, 'withdraw_freeze': 3}` | `[]` |
| `moral_dilemma` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 8, 'unknown': 5}` | `{'emocio': 3, 'instinkt': 5, 'mixed': 4, 'racio': 1}` | `{'ethical_disclosure': 13}` | `[]` |
| `public_speaking_freeze` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 9, 'mixed': 1, 'unknown': 3}` | `{'emocio': 3, 'instinkt': 8, 'mixed': 1, 'racio': 1}` | `{'delay_analyze': 4, 'withdraw_freeze': 9}` | `[]` |
| `quit_job_start_business` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 6, 'mixed': 6, 'unknown': 1}` | `{'emocio': 3, 'instinkt': 4, 'mixed': 6}` | `{'delay_analyze': 12, 'withdraw_freeze': 1}` | `[]` |
| `risky_opportunity` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'emocio': 1, 'instinkt': 10, 'unknown': 2}` | `{'emocio': 2, 'instinkt': 9, 'mixed': 2}` | `{'delay_analyze': 1, 'mixed_or_unclear': 1, 'pursue_commit': 2, 'withdraw_freeze': 9}` | `[]` |
| `romantic_return_loop` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'emocio': 1, 'instinkt': 7, 'mixed': 5}` | `{'emocio': 1, 'instinkt': 10, 'mixed': 1, 'racio': 1}` | `{'relationship_return': 13}` | `[]` |

## Quality Flags

- False positives: `['romantic_return_loop::REI']`
- False negatives: `['romantic_return_loop::E>R>I', 'boundary_violation::RI', 'boundary_violation::R>E>I', 'boundary_violation::E>I>R', 'boundary_violation::I>E>R', 'family_attachment_decision::EI', 'family_attachment_decision::REI']`
- Actionable failures: `['romantic_return_loop::E>R>I', 'boundary_violation::RI', 'boundary_violation::R>E>I', 'boundary_violation::E>I>R', 'boundary_violation::I>E>R', 'family_attachment_decision::EI', 'family_attachment_decision::REI']`
- Hard false negatives: `['boundary_violation::RI', 'boundary_violation::R>E>I', 'boundary_violation::E>I>R', 'boundary_violation::I>E>R', 'family_attachment_decision::EI', 'family_attachment_decision::REI']`
- Soft false negatives: `['romantic_return_loop::E>R>I']`
- Evaluator warnings: `['meeting_avoidance::R', 'meeting_avoidance::E', 'meeting_avoidance::I', 'meeting_avoidance::RI', 'meeting_avoidance::EI', 'meeting_avoidance::R>E>I', 'meeting_avoidance::R>I>E', 'meeting_avoidance::E>R>I', 'meeting_avoidance::E>I>R', 'meeting_avoidance::I>R>E', 'meeting_avoidance::I>E>R', 'meeting_avoidance::REI', 'romantic_return_loop::R', 'romantic_return_loop::E', 'romantic_return_loop::I', 'romantic_return_loop::RE', 'romantic_return_loop::RI', 'romantic_return_loop::EI', 'romantic_return_loop::R>E>I', 'romantic_return_loop::R>I>E', 'romantic_return_loop::E>I>R', 'romantic_return_loop::I>R>E', 'romantic_return_loop::I>E>R', 'romantic_return_loop::REI', 'risky_opportunity::R', 'risky_opportunity::E', 'risky_opportunity::I', 'risky_opportunity::RE', 'risky_opportunity::RI', 'risky_opportunity::EI', 'risky_opportunity::R>E>I', 'risky_opportunity::R>I>E', 'risky_opportunity::E>R>I', 'risky_opportunity::E>I>R', 'risky_opportunity::I>R>E', 'risky_opportunity::I>E>R', 'risky_opportunity::REI', 'creative_project_obsession::R', 'creative_project_obsession::E', 'creative_project_obsession::RE', 'creative_project_obsession::RI', 'creative_project_obsession::EI', 'creative_project_obsession::R>E>I', 'creative_project_obsession::R>I>E', 'creative_project_obsession::E>R>I', 'creative_project_obsession::E>I>R', 'creative_project_obsession::I>R>E', 'creative_project_obsession::I>E>R', 'creative_project_obsession::REI', 'boundary_violation::RI', 'boundary_violation::R>E>I', 'boundary_violation::E>I>R', 'boundary_violation::I>E>R', 'moral_dilemma::R', 'moral_dilemma::E', 'moral_dilemma::I', 'moral_dilemma::RE', 'moral_dilemma::RI', 'moral_dilemma::EI', 'moral_dilemma::R>I>E', 'moral_dilemma::E>R>I', 'moral_dilemma::E>I>R', 'moral_dilemma::I>R>E', 'moral_dilemma::I>E>R', 'moral_dilemma::REI']`
- Missing required keys: `[]`
- Processor identity violations: `[]`
- R=E=I Racio-default cases: `['conflict_with_coworker']`

## Case Table

| Scenario | Profile | Fallbacks | Tokens | Max Jaccard | Profile leader | Situational driver | Resultant | Leading | Action class | False positives | False negatives | Severity |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|
| `meeting_avoidance` | `R` | `0` | `9373` | `0.0609` | `racio` | `unknown` | `racio` | `racio` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `E` | `0` | `9564` | `0.1048` | `emocio` | `instinkt` | `emocio` | `emocio` | `mixed_or_unclear` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `I` | `0` | `9521` | `0.075` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `mixed_or_unclear` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `RE` | `0` | `9315` | `0.0709` | `mixed` | `instinkt` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `meeting_avoidance` | `RI` | `0` | `9285` | `0.0926` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `EI` | `0` | `9256` | `0.104` | `mixed` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `R>E>I` | `0` | `9321` | `0.0928` | `racio` | `instinkt` | `emocio` | `emocio` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `R>I>E` | `1` | `5562` | `0.0972` | `racio` | `unknown` | `racio` | `racio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `E>R>I` | `0` | `9447` | `0.0978` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `E>I>R` | `0` | `9434` | `0.0784` | `emocio` | `instinkt` | `emocio` | `emocio` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `I>R>E` | `0` | `9217` | `0.0526` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `mixed_or_unclear` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `I>E>R` | `0` | `9169` | `0.0673` | `instinkt` | `unknown` | `mixed` | `mixed` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `REI` | `0` | `9517` | `0.0851` | `unknown` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `quit_job_start_business` | `R` | `0` | `10109` | `0.0652` | `racio` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `E` | `0` | `9906` | `0.0694` | `emocio` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I` | `0` | `10122` | `0.12` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `RE` | `0` | `10023` | `0.0843` | `mixed` | `instinkt` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `RI` | `0` | `9987` | `0.0649` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `quit_job_start_business` | `EI` | `0` | `10067` | `0.0909` | `mixed` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `R>E>I` | `0` | `9834` | `0.0542` | `racio` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `R>I>E` | `0` | `9989` | `0.0825` | `racio` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `E>R>I` | `0` | `10248` | `0.0782` | `emocio` | `mixed` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `E>I>R` | `0` | `9619` | `0.0538` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I>R>E` | `0` | `10183` | `0.0838` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I>E>R` | `0` | `10111` | `0.0982` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `REI` | `0` | `10056` | `0.0783` | `tie` | `mixed` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `R` | `0` | `9429` | `0.0769` | `racio` | `unknown` | `racio` | `racio` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `E` | `0` | `9475` | `0.1241` | `emocio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `I` | `0` | `9310` | `0.0693` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `RE` | `0` | `9334` | `0.0991` | `mixed` | `instinkt` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `RI` | `0` | `9391` | `0.0859` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `EI` | `0` | `9226` | `0.1043` | `mixed` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `R>E>I` | `0` | `9711` | `0.0705` | `racio` | `mixed` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `R>I>E` | `0` | `9388` | `0.0935` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `E>R>I` | `0` | `9431` | `0.0924` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `E>I>R` | `0` | `9500` | `0.0692` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `I>R>E` | `0` | `9584` | `0.0526` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `I>E>R` | `0` | `9733` | `0.0792` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `REI` | `0` | `9531` | `0.0696` | `tie` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `romantic_return_loop` | `R` | `0` | `9830` | `0.1007` | `racio` | `mixed` | `racio` | `racio` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `E` | `0` | `9822` | `0.0734` | `emocio` | `instinkt` | `mixed` | `mixed` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `I` | `0` | `9728` | `0.0791` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `RE` | `0` | `9566` | `0.0916` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `RI` | `0` | `9529` | `0.1484` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `EI` | `0` | `9573` | `0.1405` | `mixed` | `mixed` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `R>E>I` | `0` | `9784` | `0.1156` | `racio` | `emocio` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `R>I>E` | `0` | `9648` | `0.0726` | `racio` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `E>R>I` | `0` | `9709` | `0.063` | `emocio` | `mixed` | `emocio` | `emocio` | `relationship_return` | none | rationalization_missing | soft_false_negative:1 |
| `romantic_return_loop` | `E>I>R` | `0` | `10015` | `0.0988` | `emocio` | `mixed` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `I>R>E` | `0` | `9634` | `0.1102` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `I>E>R` | `0` | `9525` | `0.0611` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `REI` | `0` | `9906` | `0.0588` | `tie` | `mixed` | `instinkt` | `instinkt` | `relationship_return` | boundary_pressure_on_unexpected_scenario | rationalization_missing | evaluator_warning:1 |
| `conflict_with_coworker` | `R` | `0` | `9432` | `0.0986` | `racio` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `E` | `0` | `9410` | `0.0619` | `emocio` | `instinkt` | `emocio` | `emocio` | `approach_confront` | none | none | none |
| `conflict_with_coworker` | `I` | `0` | `9436` | `0.0986` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `RE` | `0` | `9168` | `0.0777` | `mixed` | `instinkt` | `mixed` | `mixed` | `approach_confront` | none | none | none |
| `conflict_with_coworker` | `RI` | `0` | `9260` | `0.0762` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `approach_confront` | none | none | none |
| `conflict_with_coworker` | `EI` | `0` | `9468` | `0.0855` | `mixed` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `R>E>I` | `0` | `9388` | `0.1134` | `racio` | `emocio` | `racio` | `racio` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `R>I>E` | `0` | `9434` | `0.0783` | `racio` | `instinkt` | `racio` | `racio` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `E>R>I` | `0` | `9262` | `0.0874` | `emocio` | `emocio` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `E>I>R` | `0` | `9408` | `0.0972` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `I>R>E` | `0` | `9398` | `0.1145` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `I>E>R` | `0` | `9327` | `0.1455` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `REI` | `0` | `9360` | `0.098` | `tie` | `mixed` | `racio` | `racio` | `approach_confront` | none | none | none |
| `risky_opportunity` | `R` | `0` | `9273` | `0.0909` | `racio` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `E` | `0` | `9120` | `0.1205` | `emocio` | `instinkt` | `mixed` | `mixed` | `pursue_commit` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `I` | `0` | `9438` | `0.0948` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `RE` | `0` | `9772` | `0.0732` | `mixed` | `instinkt` | `mixed` | `mixed` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `RI` | `0` | `9293` | `0.0615` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `EI` | `0` | `9164` | `0.0588` | `mixed` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `R>E>I` | `0` | `9348` | `0.1146` | `racio` | `emocio` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `R>I>E` | `0` | `9251` | `0.0899` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `E>R>I` | `0` | `9485` | `0.0709` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `E>I>R` | `0` | `9392` | `0.0821` | `emocio` | `instinkt` | `emocio` | `emocio` | `pursue_commit` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `I>R>E` | `0` | `9282` | `0.1034` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `I>E>R` | `0` | `9201` | `0.0769` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `mixed_or_unclear` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `REI` | `0` | `9701` | `0.08` | `tie` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `expensive_purchase` | `R` | `0` | `9279` | `0.0963` | `racio` | `unknown` | `racio` | `racio` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `E` | `0` | `9486` | `0.0709` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `I` | `0` | `9489` | `0.075` | `instinkt` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `RE` | `0` | `9584` | `0.0776` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `RI` | `0` | `9358` | `0.0424` | `mixed` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `EI` | `0` | `9553` | `0.0486` | `mixed` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `R>E>I` | `0` | `9522` | `0.0709` | `racio` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `R>I>E` | `0` | `9546` | `0.0839` | `racio` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `E>R>I` | `0` | `9214` | `0.072` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `E>I>R` | `0` | `9606` | `0.078` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `I>R>E` | `0` | `9606` | `0.0828` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `I>E>R` | `0` | `9658` | `0.0714` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `REI` | `0` | `9322` | `0.0594` | `unknown` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `R` | `0` | `9947` | `0.0988` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `E` | `0` | `9976` | `0.1235` | `emocio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `I` | `0` | `10021` | `0.1439` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `RE` | `0` | `9912` | `0.1275` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `RI` | `0` | `10072` | `0.1509` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `EI` | `0` | `10056` | `0.1128` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `R>E>I` | `0` | `9958` | `0.0789` | `racio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `R>I>E` | `0` | `10015` | `0.1373` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `E>R>I` | `0` | `10095` | `0.125` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `grief_loss` | `E>I>R` | `0` | `10008` | `0.1151` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `I>R>E` | `0` | `10161` | `0.109` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `I>E>R` | `0` | `9824` | `0.1049` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `REI` | `0` | `10231` | `0.0784` | `unknown` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `creative_project_obsession` | `R` | `0` | `9849` | `0.0848` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `E` | `0` | `10036` | `0.1232` | `emocio` | `instinkt` | `mixed` | `mixed` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `I` | `0` | `9608` | `0.0904` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `creative_project_obsession` | `RE` | `0` | `9857` | `0.146` | `unknown` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `RI` | `0` | `9713` | `0.0985` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `EI` | `0` | `9900` | `0.1074` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `R>E>I` | `0` | `9766` | `0.0845` | `racio` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `R>I>E` | `0` | `9905` | `0.0898` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `E>R>I` | `0` | `10080` | `0.1168` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `E>I>R` | `0` | `9880` | `0.0764` | `emocio` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `I>R>E` | `0` | `9761` | `0.0786` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `I>E>R` | `0` | `9779` | `0.1053` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `REI` | `0` | `9923` | `0.0805` | `tie` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `boundary_violation` | `R` | `0` | `9441` | `0.1161` | `racio` | `instinkt` | `racio` | `racio` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `E` | `0` | `9385` | `0.1146` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `I` | `0` | `9501` | `0.0847` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `RE` | `0` | `9478` | `0.1038` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `RI` | `0` | `9411` | `0.1078` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | expected_patterns_missing,boundary_pressure_missing | hard_false_negative:1,evaluator_warning:1 |
| `boundary_violation` | `EI` | `0` | `9235` | `0.0991` | `mixed` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `R>E>I` | `0` | `9396` | `0.0917` | `racio` | `unknown` | `instinkt` | `instinkt` | `protect_boundary` | none | expected_patterns_missing,boundary_pressure_missing | hard_false_negative:1,evaluator_warning:1 |
| `boundary_violation` | `R>I>E` | `0` | `9143` | `0.1023` | `racio` | `instinkt` | `mixed` | `mixed` | `protect_boundary` | none | none | none |
| `boundary_violation` | `E>R>I` | `0` | `9455` | `0.0756` | `emocio` | `unknown` | `emocio` | `emocio` | `protect_boundary` | none | none | none |
| `boundary_violation` | `E>I>R` | `0` | `9470` | `0.1235` | `emocio` | `instinkt` | `emocio` | `emocio` | `protect_boundary` | none | expected_patterns_missing,boundary_pressure_missing | hard_false_negative:1,evaluator_warning:1 |
| `boundary_violation` | `I>R>E` | `0` | `9440` | `0.1239` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `boundary_violation` | `I>E>R` | `0` | `9264` | `0.131` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `protect_boundary` | none | expected_patterns_missing,boundary_pressure_missing | hard_false_negative:1,evaluator_warning:1 |
| `boundary_violation` | `REI` | `0` | `9409` | `0.0889` | `tie` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `moral_dilemma` | `R` | `0` | `9621` | `0.1338` | `racio` | `unknown` | `racio` | `racio` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `E` | `0` | `9840` | `0.1167` | `emocio` | `unknown` | `mixed` | `mixed` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `I` | `0` | `9693` | `0.075` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `RE` | `0` | `9676` | `0.0787` | `mixed` | `instinkt` | `mixed` | `mixed` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `RI` | `0` | `9843` | `0.1167` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `EI` | `0` | `9843` | `0.0853` | `mixed` | `unknown` | `mixed` | `mixed` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `R>E>I` | `0` | `9647` | `0.124` | `racio` | `unknown` | `mixed` | `mixed` | `ethical_disclosure` | none | none | none |
| `moral_dilemma` | `R>I>E` | `0` | `9548` | `0.078` | `racio` | `instinkt` | `instinkt` | `instinkt` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `E>R>I` | `0` | `9611` | `0.1182` | `emocio` | `instinkt` | `emocio` | `emocio` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `E>I>R` | `0` | `9765` | `0.1032` | `emocio` | `unknown` | `emocio` | `emocio` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `I>R>E` | `0` | `9710` | `0.1167` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `I>E>R` | `0` | `9813` | `0.1299` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `REI` | `0` | `9673` | `0.1167` | `tie` | `instinkt` | `emocio` | `emocio` | `ethical_disclosure` | none | rationalization_missing | evaluator_warning:1 |
| `family_attachment_decision` | `R` | `0` | `9433` | `0.093` | `racio` | `unknown` | `racio` | `racio` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `E` | `0` | `9747` | `0.128` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `I` | `0` | `9600` | `0.1345` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `RE` | `0` | `9791` | `0.1478` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `RI` | `0` | `9686` | `0.1712` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `EI` | `0` | `9621` | `0.1869` | `mixed` | `unknown` | `mixed` | `mixed` | `approach_confront` | none | boundary_pressure_missing | hard_false_negative:1 |
| `family_attachment_decision` | `R>E>I` | `0` | `9427` | `0.1382` | `racio` | `emocio` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `R>I>E` | `0` | `9508` | `0.2075` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `E>R>I` | `0` | `9556` | `0.1698` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `E>I>R` | `0` | `9748` | `0.1043` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `I>R>E` | `0` | `9489` | `0.1698` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `I>E>R` | `0` | `9837` | `0.1624` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `REI` | `0` | `9554` | `0.1103` | `unknown` | `instinkt` | `instinkt` | `instinkt` | `protect_boundary` | none | boundary_pressure_missing | hard_false_negative:1 |