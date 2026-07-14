# REI Profile Matrix Evaluation

- Run id: `20260517_214607`
- Provider: `ollama`
- Model: `granite4.1:30b`
- Context: `65536`
- GPU layers: `999`
- Cases: `156`
- Fallback count: `0`
- Missing-key case count: `0`
- Processor identity violations: `0`
- False-positive case count: `1`
- False-negative case count: `69`
- Hard false-negative case count: `6`
- Soft false-negative case count: `1`
- Evaluator-warning case count: `64`
- Total tokens: `1498792`

## Old vs New Metrics

| Metric | Previous run | Current run |
|---|---:|---:|
| `fallback_count` | `0` | `0` |
| `true_missing_required_key_count` | `0` | `0` |
| `hard_false_negative_count` | `not split` | `6` |
| `soft_false_negative_count` | `not split` | `1` |
| `false_positive_count` | `1` | `1` |
| `rei_racio_default_case_count` | `2` | `1` |
| `processor_identity_violation_count` | `0` | `0` |

## Profile Sensitivity

| Scenario | Cases | Unique Ego signatures | Identical across profiles | Profile leaders | Situational drivers | Resultants | Action classes |
|---|---:|---:|---|---|---|---|---|
| `boundary_violation` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 6, 'unknown': 7}` | `{'emocio': 3, 'instinkt': 6, 'mixed': 3, 'racio': 1}` | `{'delay_analyze': 3, 'protect_boundary': 6, 'withdraw_freeze': 4}` |
| `conflict_with_coworker` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'emocio': 3, 'instinkt': 9, 'mixed': 1}` | `{'emocio': 2, 'instinkt': 5, 'mixed': 4, 'racio': 2}` | `{'approach_confront': 3, 'delay_analyze': 1, 'withdraw_freeze': 9}` |
| `creative_project_obsession` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 12, 'mixed': 1}` | `{'emocio': 3, 'instinkt': 10}` | `{'delay_analyze': 10, 'withdraw_freeze': 3}` |
| `expensive_purchase` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'unknown': 1}` | `{'instinkt': 4, 'mixed': 1, 'unknown': 8}` | `{'emocio': 2, 'instinkt': 8, 'mixed': 3}` | `{'delay_analyze': 13}` |
| `family_attachment_decision` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 9, 'unknown': 4}` | `{'emocio': 3, 'instinkt': 7, 'mixed': 3}` | `{'approach_confront': 1, 'delay_analyze': 1, 'protect_boundary': 3, 'withdraw_freeze': 8}` |
| `grief_loss` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 12, 'mixed': 1}` | `{'emocio': 3, 'instinkt': 9, 'mixed': 1}` | `{'delay_analyze': 4, 'mixed_or_unclear': 1, 'withdraw_freeze': 8}` |
| `meeting_avoidance` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 10, 'unknown': 3}` | `{'emocio': 4, 'instinkt': 4, 'mixed': 4, 'racio': 1}` | `{'approach_confront': 8, 'mixed_or_unclear': 2, 'withdraw_freeze': 3}` |
| `moral_dilemma` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'emocio': 2, 'instinkt': 10, 'unknown': 1}` | `{'emocio': 4, 'instinkt': 7, 'racio': 2}` | `{'withdraw_freeze': 13}` |
| `public_speaking_freeze` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 7, 'mixed': 1, 'unknown': 5}` | `{'emocio': 3, 'instinkt': 7, 'mixed': 3}` | `{'delay_analyze': 3, 'withdraw_freeze': 10}` |
| `quit_job_start_business` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 6, 'mixed': 7}` | `{'emocio': 2, 'instinkt': 5, 'mixed': 5, 'racio': 1}` | `{'delay_analyze': 13}` |
| `risky_opportunity` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'unknown': 1}` | `{'instinkt': 9, 'unknown': 4}` | `{'emocio': 3, 'instinkt': 10}` | `{'delay_analyze': 2, 'mixed_or_unclear': 1, 'withdraw_freeze': 10}` |
| `romantic_return_loop` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'emocio': 2, 'instinkt': 5, 'mixed': 6}` | `{'emocio': 3, 'instinkt': 7, 'mixed': 2, 'racio': 1}` | `{'relationship_return': 13}` |

## Quality Flags

- False positives: `['meeting_avoidance::RE']`
- False negatives: `['meeting_avoidance::R', 'meeting_avoidance::E', 'meeting_avoidance::I', 'meeting_avoidance::RE', 'meeting_avoidance::RI', 'meeting_avoidance::EI', 'meeting_avoidance::R>E>I', 'meeting_avoidance::R>I>E', 'meeting_avoidance::E>R>I', 'meeting_avoidance::E>I>R', 'meeting_avoidance::I>R>E', 'meeting_avoidance::I>E>R', 'meeting_avoidance::REI', 'romantic_return_loop::R', 'romantic_return_loop::E', 'romantic_return_loop::I', 'romantic_return_loop::RE', 'romantic_return_loop::RI', 'romantic_return_loop::EI', 'romantic_return_loop::R>E>I', 'romantic_return_loop::R>I>E', 'romantic_return_loop::E>R>I', 'romantic_return_loop::E>I>R', 'romantic_return_loop::I>R>E', 'romantic_return_loop::I>E>R', 'romantic_return_loop::REI', 'conflict_with_coworker::REI', 'risky_opportunity::R', 'risky_opportunity::E', 'risky_opportunity::I', 'risky_opportunity::RE', 'risky_opportunity::RI', 'risky_opportunity::EI', 'risky_opportunity::R>E>I', 'risky_opportunity::R>I>E', 'risky_opportunity::E>R>I', 'risky_opportunity::E>I>R', 'risky_opportunity::I>R>E', 'risky_opportunity::I>E>R', 'risky_opportunity::REI', 'creative_project_obsession::R', 'creative_project_obsession::E', 'creative_project_obsession::I', 'creative_project_obsession::RE', 'creative_project_obsession::RI', 'creative_project_obsession::EI', 'creative_project_obsession::R>E>I', 'creative_project_obsession::R>I>E', 'creative_project_obsession::E>R>I', 'creative_project_obsession::E>I>R', 'creative_project_obsession::I>R>E', 'boundary_violation::RE', 'boundary_violation::E>I>R', 'moral_dilemma::R', 'moral_dilemma::E', 'moral_dilemma::I', 'moral_dilemma::RE', 'moral_dilemma::RI', 'moral_dilemma::EI', 'moral_dilemma::R>E>I', 'moral_dilemma::R>I>E', 'moral_dilemma::E>R>I', 'moral_dilemma::E>I>R', 'moral_dilemma::I>R>E', 'moral_dilemma::I>E>R', 'moral_dilemma::REI', 'family_attachment_decision::E', 'family_attachment_decision::RE', 'family_attachment_decision::R>E>I']`
- Hard false negatives: `['conflict_with_coworker::REI', 'boundary_violation::RE', 'boundary_violation::E>I>R', 'family_attachment_decision::E', 'family_attachment_decision::RE', 'family_attachment_decision::R>E>I']`
- Soft false negatives: `['romantic_return_loop::I>R>E']`
- Evaluator warnings: `['meeting_avoidance::R', 'meeting_avoidance::E', 'meeting_avoidance::I', 'meeting_avoidance::RE', 'meeting_avoidance::RI', 'meeting_avoidance::EI', 'meeting_avoidance::R>E>I', 'meeting_avoidance::R>I>E', 'meeting_avoidance::E>R>I', 'meeting_avoidance::E>I>R', 'meeting_avoidance::I>R>E', 'meeting_avoidance::I>E>R', 'meeting_avoidance::REI', 'romantic_return_loop::R', 'romantic_return_loop::E', 'romantic_return_loop::I', 'romantic_return_loop::RE', 'romantic_return_loop::RI', 'romantic_return_loop::EI', 'romantic_return_loop::R>E>I', 'romantic_return_loop::R>I>E', 'romantic_return_loop::E>R>I', 'romantic_return_loop::E>I>R', 'romantic_return_loop::I>E>R', 'romantic_return_loop::REI', 'risky_opportunity::R', 'risky_opportunity::E', 'risky_opportunity::I', 'risky_opportunity::RE', 'risky_opportunity::RI', 'risky_opportunity::EI', 'risky_opportunity::R>E>I', 'risky_opportunity::R>I>E', 'risky_opportunity::E>R>I', 'risky_opportunity::E>I>R', 'risky_opportunity::I>R>E', 'risky_opportunity::I>E>R', 'risky_opportunity::REI', 'creative_project_obsession::R', 'creative_project_obsession::E', 'creative_project_obsession::I', 'creative_project_obsession::RE', 'creative_project_obsession::RI', 'creative_project_obsession::EI', 'creative_project_obsession::R>E>I', 'creative_project_obsession::R>I>E', 'creative_project_obsession::E>R>I', 'creative_project_obsession::E>I>R', 'creative_project_obsession::I>R>E', 'boundary_violation::RE', 'boundary_violation::E>I>R', 'moral_dilemma::R', 'moral_dilemma::E', 'moral_dilemma::I', 'moral_dilemma::RE', 'moral_dilemma::RI', 'moral_dilemma::EI', 'moral_dilemma::R>E>I', 'moral_dilemma::R>I>E', 'moral_dilemma::E>R>I', 'moral_dilemma::E>I>R', 'moral_dilemma::I>R>E', 'moral_dilemma::I>E>R', 'moral_dilemma::REI']`
- Missing required keys: `[]`
- Processor identity violations: `[]`
- R=E=I Racio-default cases: `['quit_job_start_business']`

## Case Table

| Scenario | Profile | Fallbacks | Tokens | Max Jaccard | Profile leader | Situational driver | Resultant | Leading | Action class | False positives | False negatives | Severity |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|
| `meeting_avoidance` | `R` | `0` | `9048` | `0.0737` | `racio` | `unknown` | `racio` | `racio` | `mixed_or_unclear` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `E` | `0` | `9052` | `0.0973` | `emocio` | `instinkt` | `emocio` | `emocio` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `I` | `0` | `9203` | `0.1205` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `RE` | `0` | `9181` | `0.1031` | `mixed` | `instinkt` | `mixed` | `mixed` | `withdraw_freeze` | boundary_pressure_on_unexpected_scenario | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `RI` | `0` | `8862` | `0.1266` | `mixed` | `instinkt` | `mixed` | `mixed` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `EI` | `0` | `9373` | `0.0957` | `mixed` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `R>E>I` | `0` | `9400` | `0.066` | `racio` | `instinkt` | `emocio` | `emocio` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `R>I>E` | `0` | `9163` | `0.07` | `racio` | `instinkt` | `instinkt` | `instinkt` | `mixed_or_unclear` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `E>R>I` | `0` | `9436` | `0.0866` | `emocio` | `instinkt` | `emocio` | `emocio` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `E>I>R` | `0` | `9238` | `0.0962` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `I>R>E` | `0` | `9429` | `0.0531` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `I>E>R` | `0` | `9182` | `0.1139` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `REI` | `0` | `9326` | `0.0901` | `tie` | `instinkt` | `mixed` | `mixed` | `approach_confront` | none | rationalization_missing | evaluator_warning:1 |
| `quit_job_start_business` | `R` | `0` | `10162` | `0.0904` | `racio` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `E` | `0` | `10094` | `0.0847` | `emocio` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I` | `0` | `9998` | `0.0809` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `RE` | `0` | `9651` | `0.1008` | `mixed` | `instinkt` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `RI` | `0` | `9893` | `0.0769` | `mixed` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `EI` | `0` | `9945` | `0.0814` | `mixed` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `R>E>I` | `0` | `10035` | `0.0968` | `racio` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `R>I>E` | `0` | `10345` | `0.0889` | `racio` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `E>R>I` | `0` | `9747` | `0.0789` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `E>I>R` | `0` | `10059` | `0.0718` | `emocio` | `mixed` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I>R>E` | `0` | `9818` | `0.0855` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I>E>R` | `0` | `9904` | `0.0828` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `REI` | `0` | `10169` | `0.0783` | `tie` | `mixed` | `racio` | `racio` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `R` | `0` | `9443` | `0.0902` | `racio` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `E` | `0` | `9408` | `0.0885` | `emocio` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `I` | `0` | `9505` | `0.0547` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `RE` | `0` | `9392` | `0.0753` | `mixed` | `instinkt` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `RI` | `0` | `9472` | `0.0729` | `mixed` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `EI` | `0` | `9428` | `0.048` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `R>E>I` | `0` | `9534` | `0.0441` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `R>I>E` | `0` | `9434` | `0.1043` | `racio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `E>R>I` | `0` | `9506` | `0.1367` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `E>I>R` | `0` | `9392` | `0.1168` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `I>R>E` | `0` | `9439` | `0.0825` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `I>E>R` | `0` | `9342` | `0.0661` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `REI` | `0` | `9496` | `0.117` | `tie` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `romantic_return_loop` | `R` | `0` | `9728` | `0.0878` | `racio` | `mixed` | `racio` | `racio` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `E` | `0` | `9680` | `0.1111` | `emocio` | `mixed` | `mixed` | `mixed` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `I` | `0` | `9835` | `0.0658` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `RE` | `0` | `9710` | `0.0909` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `RI` | `0` | `9429` | `0.1085` | `mixed` | `emocio` | `mixed` | `mixed` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `EI` | `0` | `9764` | `0.0714` | `mixed` | `mixed` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `R>E>I` | `0` | `9573` | `0.1043` | `racio` | `mixed` | `emocio` | `emocio` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `R>I>E` | `0` | `9559` | `0.0882` | `racio` | `mixed` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `E>R>I` | `0` | `9658` | `0.0821` | `emocio` | `emocio` | `emocio` | `emocio` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `E>I>R` | `0` | `9560` | `0.0752` | `emocio` | `instinkt` | `emocio` | `emocio` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `I>R>E` | `0` | `9704` | `0.0909` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | soft_false_negative:1 |
| `romantic_return_loop` | `I>E>R` | `0` | `9544` | `0.0863` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `romantic_return_loop` | `REI` | `0` | `9865` | `0.1181` | `tie` | `mixed` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | evaluator_warning:1 |
| `conflict_with_coworker` | `R` | `0` | `9318` | `0.0945` | `racio` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `E` | `0` | `9480` | `0.0985` | `emocio` | `instinkt` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `I` | `0` | `9398` | `0.0851` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `RE` | `0` | `9391` | `0.0561` | `mixed` | `instinkt` | `mixed` | `mixed` | `approach_confront` | none | none | none |
| `conflict_with_coworker` | `RI` | `0` | `9359` | `0.0625` | `mixed` | `emocio` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `EI` | `0` | `9646` | `0.094` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `R>E>I` | `0` | `9292` | `0.0787` | `racio` | `emocio` | `racio` | `racio` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `R>I>E` | `0` | `9264` | `0.1207` | `racio` | `instinkt` | `racio` | `racio` | `approach_confront` | none | none | none |
| `conflict_with_coworker` | `E>R>I` | `0` | `9361` | `0.1154` | `emocio` | `emocio` | `emocio` | `emocio` | `approach_confront` | none | none | none |
| `conflict_with_coworker` | `E>I>R` | `0` | `9400` | `0.1121` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `I>R>E` | `0` | `9418` | `0.1241` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `I>E>R` | `0` | `9461` | `0.082` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `REI` | `0` | `9640` | `0.0602` | `tie` | `instinkt` | `mixed` | `mixed` | `delay_analyze` | none | boundary_pressure_missing | hard_false_negative:1 |
| `risky_opportunity` | `R` | `0` | `9395` | `0.1094` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `E` | `0` | `9423` | `0.0935` | `emocio` | `unknown` | `emocio` | `emocio` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `I` | `0` | `9409` | `0.0877` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `RE` | `0` | `9369` | `0.0874` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `mixed_or_unclear` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `RI` | `0` | `9547` | `0.0987` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `EI` | `0` | `9615` | `0.0725` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `R>E>I` | `0` | `9322` | `0.099` | `racio` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `R>I>E` | `0` | `9437` | `0.0748` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `E>R>I` | `0` | `9261` | `0.0857` | `emocio` | `unknown` | `emocio` | `emocio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `E>I>R` | `0` | `9446` | `0.0787` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `I>R>E` | `0` | `9387` | `0.1165` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `I>E>R` | `0` | `9270` | `0.075` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `risky_opportunity` | `REI` | `0` | `9775` | `0.0909` | `unknown` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `expensive_purchase` | `R` | `0` | `9444` | `0.0726` | `racio` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `E` | `0` | `9454` | `0.0593` | `emocio` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `I` | `0` | `8970` | `0.0783` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `RE` | `0` | `9233` | `0.0909` | `mixed` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `RI` | `0` | `9451` | `0.098` | `mixed` | `instinkt` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `EI` | `0` | `9554` | `0.0515` | `mixed` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `R>E>I` | `0` | `9160` | `0.0763` | `racio` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `R>I>E` | `0` | `9225` | `0.0645` | `racio` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `E>R>I` | `0` | `9305` | `0.0775` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `E>I>R` | `0` | `9509` | `0.0638` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `I>R>E` | `0` | `9313` | `0.0561` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `I>E>R` | `0` | `9286` | `0.0603` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `REI` | `0` | `9393` | `0.0756` | `unknown` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `R` | `0` | `9582` | `0.1367` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `E` | `0` | `10426` | `0.0851` | `emocio` | `instinkt` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `I` | `0` | `10225` | `0.0988` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `RE` | `0` | `10162` | `0.1342` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `RI` | `0` | `10322` | `0.092` | `mixed` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `EI` | `0` | `10015` | `0.1081` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `R>E>I` | `0` | `10354` | `0.0922` | `racio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `R>I>E` | `0` | `10097` | `0.1304` | `racio` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `grief_loss` | `E>R>I` | `0` | `9935` | `0.1439` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `E>I>R` | `0` | `10382` | `0.1333` | `emocio` | `instinkt` | `emocio` | `emocio` | `mixed_or_unclear` | none | none | none |
| `grief_loss` | `I>R>E` | `0` | `10077` | `0.1338` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `I>E>R` | `0` | `10109` | `0.105` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `REI` | `0` | `10196` | `0.1127` | `tie` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `creative_project_obsession` | `R` | `0` | `9765` | `0.0811` | `racio` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `E` | `0` | `9798` | `0.1214` | `emocio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `I` | `0` | `9808` | `0.0909` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `RE` | `0` | `9908` | `0.1032` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `RI` | `0` | `9675` | `0.0758` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `EI` | `0` | `9825` | `0.1042` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `R>E>I` | `0` | `9969` | `0.1022` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `R>I>E` | `0` | `9888` | `0.0769` | `racio` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `E>R>I` | `0` | `9996` | `0.1034` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `E>I>R` | `0` | `9907` | `0.0692` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `I>R>E` | `0` | `9770` | `0.0857` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | evaluator_warning:1 |
| `creative_project_obsession` | `I>E>R` | `0` | `9787` | `0.0884` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `creative_project_obsession` | `REI` | `0` | `9964` | `0.0839` | `tie` | `mixed` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `boundary_violation` | `R` | `0` | `9327` | `0.1059` | `racio` | `unknown` | `racio` | `racio` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `E` | `0` | `9554` | `0.0968` | `emocio` | `unknown` | `mixed` | `mixed` | `protect_boundary` | none | none | none |
| `boundary_violation` | `I` | `0` | `9446` | `0.1019` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `RE` | `0` | `9230` | `0.0777` | `mixed` | `instinkt` | `mixed` | `mixed` | `protect_boundary` | none | expected_patterns_missing,boundary_pressure_missing | hard_false_negative:1,evaluator_warning:1 |
| `boundary_violation` | `RI` | `0` | `9320` | `0.0889` | `mixed` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `EI` | `0` | `9519` | `0.113` | `mixed` | `unknown` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `boundary_violation` | `R>E>I` | `0` | `9533` | `0.0976` | `racio` | `instinkt` | `emocio` | `emocio` | `protect_boundary` | none | none | none |
| `boundary_violation` | `R>I>E` | `0` | `9470` | `0.0899` | `racio` | `instinkt` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `boundary_violation` | `E>R>I` | `0` | `9483` | `0.1081` | `emocio` | `instinkt` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `boundary_violation` | `E>I>R` | `0` | `9344` | `0.0932` | `emocio` | `unknown` | `emocio` | `emocio` | `withdraw_freeze` | none | expected_patterns_missing,boundary_pressure_missing | hard_false_negative:1,evaluator_warning:1 |
| `boundary_violation` | `I>R>E` | `0` | `9529` | `0.0887` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `boundary_violation` | `I>E>R` | `0` | `9452` | `0.0763` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `boundary_violation` | `REI` | `0` | `9786` | `0.1047` | `tie` | `instinkt` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `moral_dilemma` | `R` | `0` | `9537` | `0.0992` | `racio` | `emocio` | `racio` | `racio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `E` | `0` | `9857` | `0.122` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `I` | `0` | `9625` | `0.1339` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `RE` | `0` | `9598` | `0.1417` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `RI` | `0` | `9622` | `0.1212` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `EI` | `0` | `9472` | `0.1186` | `mixed` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `R>E>I` | `0` | `9535` | `0.1008` | `racio` | `emocio` | `racio` | `racio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `R>I>E` | `0` | `9709` | `0.1087` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `E>R>I` | `0` | `9921` | `0.1259` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `E>I>R` | `0` | `9691` | `0.0776` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `I>R>E` | `0` | `9520` | `0.1111` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `I>E>R` | `0` | `9652` | `0.1333` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `moral_dilemma` | `REI` | `0` | `9716` | `0.0866` | `tie` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `family_attachment_decision` | `R` | `0` | `9520` | `0.1094` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `E` | `0` | `9711` | `0.1387` | `emocio` | `instinkt` | `emocio` | `emocio` | `approach_confront` | none | boundary_pressure_missing | hard_false_negative:1 |
| `family_attachment_decision` | `I` | `0` | `9403` | `0.1569` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `RE` | `0` | `9402` | `0.1574` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `protect_boundary` | none | boundary_pressure_missing | hard_false_negative:1 |
| `family_attachment_decision` | `RI` | `0` | `9710` | `0.1552` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `EI` | `0` | `9747` | `0.1538` | `mixed` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `family_attachment_decision` | `R>E>I` | `0` | `9699` | `0.1552` | `racio` | `instinkt` | `mixed` | `mixed` | `protect_boundary` | none | boundary_pressure_missing | hard_false_negative:1 |
| `family_attachment_decision` | `R>I>E` | `0` | `9796` | `0.1197` | `racio` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `E>R>I` | `0` | `9841` | `0.1545` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `E>I>R` | `0` | `9686` | `0.1217` | `emocio` | `instinkt` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `I>R>E` | `0` | `9882` | `0.1261` | `instinkt` | `instinkt` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `I>E>R` | `0` | `9620` | `0.1653` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `REI` | `0` | `9891` | `0.119` | `tie` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |