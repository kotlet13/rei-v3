# REI Profile Matrix Evaluation

- Run id: `20260627_121704`
- Provider: `ollama`
- Model: `gemma4:26b`
- Context: `65536`
- GPU layers: `999`
- Cases: `156`
- Fallback count: `1`
- Missing-key case count: `58`
- Processor identity violations: `0`
- False-positive case count: `0`
- False-negative case count: `34`
- Hard false-negative case count: `0`
- Soft false-negative case count: `34`
- Actionable failure case count: `34`
- Evaluator-warning case count: `2`
- Total tokens: `1813446`

## Old vs New Metrics

| Metric | Previous run | Current run |
|---|---:|---:|
| `fallback_count` | `0` | `1` |
| `true_missing_required_key_count` | `0` | `58` |
| `hard_false_negative_count` | `not split` | `0` |
| `soft_false_negative_count` | `not split` | `34` |
| `actionable_failure_count` | `not split` | `34` |
| `false_positive_count` | `1` | `0` |
| `rei_racio_default_case_count` | `2` | `0` |
| `processor_identity_violation_count` | `0` | `0` |

## Profile Sensitivity

| Scenario | Cases | Unique Ego signatures | Identical across profiles | Profile leaders | Situational drivers | Resultants | Action classes | Semantic diversity flags |
|---|---:|---:|---|---|---|---|---|---|
| `boundary_violation` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'mixed': 1, 'unknown': 12}` | `{'emocio': 1, 'instinkt': 1, 'mixed': 11}` | `{'approach_confront': 1, 'protect_boundary': 5, 'withdraw_freeze': 7}` | `[]` |
| `conflict_with_coworker` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 1, 'mixed': 2, 'unknown': 10}` | `{'emocio': 1, 'instinkt': 3, 'mixed': 9}` | `{'approach_confront': 2, 'withdraw_freeze': 11}` | `[]` |
| `creative_project_obsession` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'emocio': 1, 'mixed': 3, 'unknown': 9}` | `{'emocio': 1, 'instinkt': 5, 'mixed': 7}` | `{'mixed_or_unclear': 1, 'protect_boundary': 2, 'withdraw_freeze': 10}` | `[]` |
| `expensive_purchase` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'mixed': 5, 'unknown': 8}` | `{'emocio': 2, 'instinkt': 2, 'mixed': 9}` | `{'delay_analyze': 13}` | `[]` |
| `family_attachment_decision` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'emocio': 1, 'mixed': 1, 'unknown': 11}` | `{'emocio': 2, 'instinkt': 5, 'mixed': 6}` | `{'approach_confront': 4, 'mixed_or_unclear': 2, 'protect_boundary': 5, 'withdraw_freeze': 2}` | `[]` |
| `grief_loss` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'mixed': 3, 'unknown': 10}` | `{'emocio': 2, 'instinkt': 4, 'mixed': 7}` | `{'approach_confront': 1, 'protect_boundary': 1, 'withdraw_freeze': 11}` | `[]` |
| `meeting_avoidance` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'unknown': 13}` | `{'emocio': 2, 'instinkt': 5, 'mixed': 6}` | `{'approach_confront': 4, 'delay_analyze': 5, 'mixed_or_unclear': 3, 'withdraw_freeze': 1}` | `[]` |
| `moral_dilemma` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'mixed': 8, 'unknown': 5}` | `{'emocio': 2, 'instinkt': 2, 'mixed': 8, 'racio': 1}` | `{'ethical_disclosure': 12, 'mixed_or_unclear': 1}` | `[]` |
| `public_speaking_freeze` | `13` | `12` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 1, 'mixed': 7, 'unknown': 5}` | `{'instinkt': 11, 'mixed': 2}` | `{'withdraw_freeze': 13}` | `[]` |
| `quit_job_start_business` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'mixed': 13}` | `{'emocio': 1, 'instinkt': 8, 'mixed': 4}` | `{'delay_analyze': 13}` | `[]` |
| `risky_opportunity` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'emocio': 1, 'mixed': 1, 'unknown': 11}` | `{'emocio': 2, 'instinkt': 4, 'mixed': 7}` | `{'delay_analyze': 8, 'withdraw_freeze': 5}` | `[]` |
| `romantic_return_loop` | `13` | `13` | `False` | `{'emocio': 3, 'instinkt': 3, 'mixed': 3, 'racio': 3, 'tie': 1}` | `{'instinkt': 1, 'mixed': 8, 'unknown': 4}` | `{'emocio': 1, 'instinkt': 5, 'mixed': 7}` | `{'relationship_return': 13}` | `[]` |

## Quality Flags

- False positives: `[]`
- False negatives: `['meeting_avoidance::R', 'meeting_avoidance::RE', 'meeting_avoidance::EI', 'meeting_avoidance::I>R>E', 'romantic_return_loop::E', 'romantic_return_loop::RI', 'romantic_return_loop::R>I>E', 'romantic_return_loop::E>I>R', 'romantic_return_loop::I>E>R', 'risky_opportunity::E', 'risky_opportunity::I', 'risky_opportunity::RI', 'risky_opportunity::EI', 'risky_opportunity::R>I>E', 'risky_opportunity::E>R>I', 'risky_opportunity::I>E>R', 'creative_project_obsession::R', 'creative_project_obsession::E', 'creative_project_obsession::I', 'creative_project_obsession::RE', 'creative_project_obsession::RI', 'creative_project_obsession::EI', 'creative_project_obsession::R>I>E', 'creative_project_obsession::E>R>I', 'creative_project_obsession::E>I>R', 'creative_project_obsession::I>R>E', 'creative_project_obsession::I>E>R', 'creative_project_obsession::REI', 'moral_dilemma::R', 'moral_dilemma::EI', 'moral_dilemma::R>E>I', 'moral_dilemma::R>I>E', 'moral_dilemma::I>E>R', 'moral_dilemma::REI']`
- Actionable failures: `['meeting_avoidance::R', 'meeting_avoidance::RE', 'meeting_avoidance::EI', 'meeting_avoidance::I>R>E', 'romantic_return_loop::E', 'romantic_return_loop::RI', 'romantic_return_loop::R>I>E', 'romantic_return_loop::E>I>R', 'romantic_return_loop::I>E>R', 'risky_opportunity::E', 'risky_opportunity::I', 'risky_opportunity::RI', 'risky_opportunity::EI', 'risky_opportunity::R>I>E', 'risky_opportunity::E>R>I', 'risky_opportunity::I>E>R', 'creative_project_obsession::R', 'creative_project_obsession::E', 'creative_project_obsession::I', 'creative_project_obsession::RE', 'creative_project_obsession::RI', 'creative_project_obsession::EI', 'creative_project_obsession::R>I>E', 'creative_project_obsession::E>R>I', 'creative_project_obsession::E>I>R', 'creative_project_obsession::I>R>E', 'creative_project_obsession::I>E>R', 'creative_project_obsession::REI', 'moral_dilemma::R', 'moral_dilemma::EI', 'moral_dilemma::R>E>I', 'moral_dilemma::R>I>E', 'moral_dilemma::I>E>R', 'moral_dilemma::REI']`
- Hard false negatives: `[]`
- Soft false negatives: `['meeting_avoidance::R', 'meeting_avoidance::RE', 'meeting_avoidance::EI', 'meeting_avoidance::I>R>E', 'romantic_return_loop::E', 'romantic_return_loop::RI', 'romantic_return_loop::R>I>E', 'romantic_return_loop::E>I>R', 'romantic_return_loop::I>E>R', 'risky_opportunity::E', 'risky_opportunity::I', 'risky_opportunity::RI', 'risky_opportunity::EI', 'risky_opportunity::R>I>E', 'risky_opportunity::E>R>I', 'risky_opportunity::I>E>R', 'creative_project_obsession::R', 'creative_project_obsession::E', 'creative_project_obsession::I', 'creative_project_obsession::RE', 'creative_project_obsession::RI', 'creative_project_obsession::EI', 'creative_project_obsession::R>I>E', 'creative_project_obsession::E>R>I', 'creative_project_obsession::E>I>R', 'creative_project_obsession::I>R>E', 'creative_project_obsession::I>E>R', 'creative_project_obsession::REI', 'moral_dilemma::R', 'moral_dilemma::EI', 'moral_dilemma::R>E>I', 'moral_dilemma::R>I>E', 'moral_dilemma::I>E>R', 'moral_dilemma::REI']`
- Evaluator warnings: `['meeting_avoidance::E', 'meeting_avoidance::I']`
- Missing required keys: `['meeting_avoidance::R', 'meeting_avoidance::E', 'meeting_avoidance::I', 'meeting_avoidance::RE', 'meeting_avoidance::RI', 'meeting_avoidance::EI', 'meeting_avoidance::R>E>I', 'meeting_avoidance::R>I>E', 'meeting_avoidance::E>R>I', 'meeting_avoidance::REI', 'romantic_return_loop::EI', 'romantic_return_loop::R>I>E', 'conflict_with_coworker::E', 'conflict_with_coworker::RE', 'conflict_with_coworker::EI', 'conflict_with_coworker::R>E>I', 'conflict_with_coworker::E>R>I', 'conflict_with_coworker::E>I>R', 'conflict_with_coworker::I>R>E', 'conflict_with_coworker::I>E>R', 'risky_opportunity::RI', 'risky_opportunity::R>I>E', 'risky_opportunity::I>R>E', 'risky_opportunity::REI', 'expensive_purchase::RE', 'expensive_purchase::RI', 'expensive_purchase::EI', 'expensive_purchase::R>I>E', 'expensive_purchase::E>I>R', 'expensive_purchase::I>E>R', 'grief_loss::RI', 'grief_loss::REI', 'creative_project_obsession::R>E>I', 'creative_project_obsession::R>I>E', 'creative_project_obsession::E>I>R', 'boundary_violation::E', 'moral_dilemma::R', 'moral_dilemma::E', 'moral_dilemma::I', 'moral_dilemma::RE', 'moral_dilemma::RI', 'moral_dilemma::EI', 'moral_dilemma::R>I>E', 'moral_dilemma::E>R>I', 'moral_dilemma::E>I>R', 'moral_dilemma::I>R>E', 'moral_dilemma::I>E>R', 'family_attachment_decision::R', 'family_attachment_decision::E', 'family_attachment_decision::I', 'family_attachment_decision::RE', 'family_attachment_decision::RI', 'family_attachment_decision::EI', 'family_attachment_decision::R>I>E', 'family_attachment_decision::E>R>I', 'family_attachment_decision::E>I>R', 'family_attachment_decision::I>R>E', 'family_attachment_decision::I>E>R']`
- Processor identity violations: `[]`
- R=E=I Racio-default cases: `[]`

## Case Table

| Scenario | Profile | Fallbacks | Tokens | Max Jaccard | Profile leader | Situational driver | Resultant | Leading | Action class | False positives | False negatives | Severity |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|
| `meeting_avoidance` | `R` | `0` | `12547` | `0.0761` | `racio` | `unknown` | `instinkt` | `instinkt` | `approach_confront` | none | rationalization_missing | soft_false_negative:1 |
| `meeting_avoidance` | `E` | `0` | `12529` | `0.0341` | `emocio` | `unknown` | `emocio` | `emocio` | `mixed_or_unclear` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `I` | `0` | `12362` | `0.0732` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | evaluator_warning:1 |
| `meeting_avoidance` | `RE` | `0` | `12682` | `0.0323` | `mixed` | `unknown` | `emocio` | `emocio` | `delay_analyze` | none | rationalization_missing | soft_false_negative:1 |
| `meeting_avoidance` | `RI` | `0` | `12618` | `0.1` | `mixed` | `unknown` | `instinkt` | `instinkt` | `mixed_or_unclear` | none | none | none |
| `meeting_avoidance` | `EI` | `0` | `12423` | `0.0659` | `mixed` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | soft_false_negative:1 |
| `meeting_avoidance` | `R>E>I` | `0` | `12809` | `0.0918` | `racio` | `unknown` | `mixed` | `mixed` | `approach_confront` | none | none | none |
| `meeting_avoidance` | `R>I>E` | `0` | `12573` | `0.0652` | `racio` | `unknown` | `mixed` | `mixed` | `mixed_or_unclear` | none | none | none |
| `meeting_avoidance` | `E>R>I` | `0` | `12687` | `0.069` | `emocio` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `meeting_avoidance` | `E>I>R` | `0` | `10495` | `0.0543` | `emocio` | `unknown` | `mixed` | `mixed` | `approach_confront` | none | none | none |
| `meeting_avoidance` | `I>R>E` | `0` | `10511` | `0.0667` | `instinkt` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | rationalization_missing | soft_false_negative:1 |
| `meeting_avoidance` | `I>E>R` | `0` | `10619` | `0.0879` | `instinkt` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `meeting_avoidance` | `REI` | `0` | `13051` | `0.0734` | `tie` | `unknown` | `instinkt` | `instinkt` | `approach_confront` | none | none | none |
| `quit_job_start_business` | `R` | `0` | `10839` | `0.048` | `racio` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `E` | `0` | `10725` | `0.0571` | `emocio` | `mixed` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I` | `0` | `10649` | `0.0377` | `instinkt` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `RE` | `0` | `10744` | `0.0642` | `mixed` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `RI` | `0` | `10837` | `0.0417` | `mixed` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `EI` | `0` | `10729` | `0.0472` | `mixed` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `R>E>I` | `0` | `10746` | `0.0526` | `racio` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `R>I>E` | `0` | `10770` | `0.0472` | `racio` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `E>R>I` | `0` | `10849` | `0.049` | `emocio` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `E>I>R` | `0` | `10854` | `0.0588` | `emocio` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I>R>E` | `0` | `10878` | `0.0404` | `instinkt` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `I>E>R` | `0` | `10930` | `0.0467` | `instinkt` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `quit_job_start_business` | `REI` | `0` | `11113` | `0.0495` | `tie` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `public_speaking_freeze` | `R` | `0` | `10575` | `0.0777` | `racio` | `mixed` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `E` | `0` | `10731` | `0.0841` | `emocio` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `I` | `0` | `10504` | `0.099` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `RE` | `0` | `10544` | `0.0909` | `mixed` | `mixed` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `RI` | `0` | `10759` | `0.045` | `mixed` | `mixed` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `EI` | `0` | `10534` | `0.08` | `mixed` | `mixed` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `R>E>I` | `0` | `10825` | `0.0526` | `racio` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `R>I>E` | `0` | `10741` | `0.0693` | `racio` | `mixed` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `E>R>I` | `0` | `10808` | `0.0642` | `emocio` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `E>I>R` | `0` | `10504` | `0.0854` | `emocio` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `I>R>E` | `0` | `10608` | `0.1075` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `I>E>R` | `0` | `10781` | `0.0928` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `public_speaking_freeze` | `REI` | `0` | `10736` | `0.125` | `tie` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `romantic_return_loop` | `R` | `0` | `10960` | `0.0517` | `racio` | `mixed` | `instinkt` | `instinkt` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `E` | `0` | `10924` | `0.0455` | `emocio` | `mixed` | `emocio` | `emocio` | `relationship_return` | none | rationalization_missing | soft_false_negative:1 |
| `romantic_return_loop` | `I` | `0` | `10932` | `0.0354` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `RE` | `0` | `10874` | `0.0476` | `mixed` | `mixed` | `instinkt` | `instinkt` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `RI` | `0` | `10871` | `0.0536` | `mixed` | `mixed` | `instinkt` | `instinkt` | `relationship_return` | none | rationalization_missing | soft_false_negative:1 |
| `romantic_return_loop` | `EI` | `0` | `12887` | `0.05` | `mixed` | `mixed` | `instinkt` | `instinkt` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `R>E>I` | `0` | `11057` | `0.0438` | `racio` | `mixed` | `mixed` | `mixed` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `R>I>E` | `0` | `15540` | `0.0463` | `racio` | `instinkt` | `mixed` | `mixed` | `relationship_return` | none | rationalization_missing | soft_false_negative:1 |
| `romantic_return_loop` | `E>R>I` | `0` | `11058` | `0.063` | `emocio` | `mixed` | `mixed` | `mixed` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `E>I>R` | `0` | `10995` | `0.0376` | `emocio` | `mixed` | `mixed` | `mixed` | `relationship_return` | none | rationalization_missing | soft_false_negative:1 |
| `romantic_return_loop` | `I>R>E` | `0` | `10971` | `0.0484` | `instinkt` | `unknown` | `mixed` | `mixed` | `relationship_return` | none | none | none |
| `romantic_return_loop` | `I>E>R` | `0` | `10955` | `0.0467` | `instinkt` | `unknown` | `mixed` | `mixed` | `relationship_return` | none | rationalization_missing | soft_false_negative:1 |
| `romantic_return_loop` | `REI` | `0` | `11153` | `0.0513` | `tie` | `unknown` | `mixed` | `mixed` | `relationship_return` | none | none | none |
| `conflict_with_coworker` | `R` | `0` | `10675` | `0.0789` | `racio` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `E` | `0` | `12795` | `0.0632` | `emocio` | `unknown` | `mixed` | `mixed` | `approach_confront` | none | none | none |
| `conflict_with_coworker` | `I` | `0` | `10721` | `0.0909` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `approach_confront` | none | none | none |
| `conflict_with_coworker` | `RE` | `0` | `12849` | `0.1016` | `mixed` | `unknown` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `RI` | `0` | `10815` | `0.0763` | `mixed` | `instinkt` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `EI` | `0` | `13050` | `0.0396` | `mixed` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `R>E>I` | `0` | `12700` | `0.0482` | `racio` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `R>I>E` | `0` | `10917` | `0.0684` | `racio` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `E>R>I` | `0` | `12901` | `0.088` | `emocio` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `E>I>R` | `0` | `12774` | `0.0818` | `emocio` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `I>R>E` | `0` | `12803` | `0.0513` | `instinkt` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `I>E>R` | `0` | `12666` | `0.0982` | `instinkt` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `conflict_with_coworker` | `REI` | `0` | `10977` | `0.1169` | `tie` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `risky_opportunity` | `R` | `0` | `10717` | `0.0783` | `racio` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `risky_opportunity` | `E` | `0` | `10687` | `0.0686` | `emocio` | `unknown` | `emocio` | `emocio` | `delay_analyze` | none | rationalization_missing | soft_false_negative:1 |
| `risky_opportunity` | `I` | `0` | `10647` | `0.0978` | `instinkt` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | rationalization_missing | soft_false_negative:1 |
| `risky_opportunity` | `RE` | `0` | `10610` | `0.0893` | `mixed` | `unknown` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `risky_opportunity` | `RI` | `0` | `13595` | `0.0971` | `mixed` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | rationalization_missing | soft_false_negative:1 |
| `risky_opportunity` | `EI` | `0` | `10637` | `0.0865` | `mixed` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | soft_false_negative:1 |
| `risky_opportunity` | `R>E>I` | `0` | `10761` | `0.1071` | `racio` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `risky_opportunity` | `R>I>E` | `0` | `12739` | `0.08` | `racio` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | rationalization_missing | soft_false_negative:1 |
| `risky_opportunity` | `E>R>I` | `0` | `10752` | `0.0729` | `emocio` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | rationalization_missing | soft_false_negative:1 |
| `risky_opportunity` | `E>I>R` | `0` | `10890` | `0.0796` | `emocio` | `emocio` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `risky_opportunity` | `I>R>E` | `0` | `13412` | `0.1011` | `instinkt` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `risky_opportunity` | `I>E>R` | `0` | `10611` | `0.0654` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | soft_false_negative:1 |
| `risky_opportunity` | `REI` | `0` | `13094` | `0.1008` | `tie` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `expensive_purchase` | `R` | `0` | `10685` | `0.0808` | `racio` | `mixed` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `E` | `0` | `10765` | `0.0505` | `emocio` | `unknown` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `I` | `0` | `10711` | `0.068` | `instinkt` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `RE` | `1` | `15552` | `0.0795` | `mixed` | `mixed` | `emocio` | `emocio` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `RI` | `0` | `12664` | `0.0556` | `mixed` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `EI` | `0` | `12567` | `0.0455` | `mixed` | `unknown` | `instinkt` | `instinkt` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `R>E>I` | `0` | `10810` | `0.0659` | `racio` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `R>I>E` | `0` | `12608` | `0.0412` | `racio` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `E>R>I` | `0` | `10636` | `0.0476` | `emocio` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `E>I>R` | `0` | `13761` | `0.0619` | `emocio` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `I>R>E` | `0` | `10851` | `0.0426` | `instinkt` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `I>E>R` | `0` | `12741` | `0.05` | `instinkt` | `unknown` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `expensive_purchase` | `REI` | `0` | `11142` | `0.0583` | `tie` | `mixed` | `mixed` | `mixed` | `delay_analyze` | none | none | none |
| `grief_loss` | `R` | `0` | `11043` | `0.0963` | `racio` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `E` | `0` | `10883` | `0.094` | `emocio` | `unknown` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `I` | `0` | `10733` | `0.0667` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `RE` | `0` | `10756` | `0.0714` | `mixed` | `mixed` | `emocio` | `emocio` | `approach_confront` | none | none | none |
| `grief_loss` | `RI` | `0` | `13448` | `0.0965` | `mixed` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `EI` | `0` | `10882` | `0.0887` | `mixed` | `unknown` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `grief_loss` | `R>E>I` | `0` | `11057` | `0.1136` | `racio` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `R>I>E` | `0` | `11093` | `0.0806` | `racio` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `E>R>I` | `0` | `10996` | `0.1128` | `emocio` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `E>I>R` | `0` | `10907` | `0.0901` | `emocio` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `I>R>E` | `0` | `11043` | `0.1328` | `instinkt` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `I>E>R` | `0` | `11052` | `0.119` | `instinkt` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `grief_loss` | `REI` | `0` | `14047` | `0.062` | `tie` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `creative_project_obsession` | `R` | `0` | `10689` | `0.08` | `racio` | `unknown` | `instinkt` | `instinkt` | `mixed_or_unclear` | none | rationalization_missing | soft_false_negative:1 |
| `creative_project_obsession` | `E` | `0` | `10741` | `0.0476` | `emocio` | `unknown` | `emocio` | `emocio` | `withdraw_freeze` | none | rationalization_missing | soft_false_negative:1 |
| `creative_project_obsession` | `I` | `0` | `10819` | `0.0446` | `instinkt` | `unknown` | `mixed` | `mixed` | `protect_boundary` | none | rationalization_missing | soft_false_negative:1 |
| `creative_project_obsession` | `RE` | `0` | `10706` | `0.0545` | `mixed` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | rationalization_missing | soft_false_negative:1 |
| `creative_project_obsession` | `RI` | `0` | `10887` | `0.0467` | `mixed` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | soft_false_negative:1 |
| `creative_project_obsession` | `EI` | `0` | `10762` | `0.0577` | `mixed` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | soft_false_negative:1 |
| `creative_project_obsession` | `R>E>I` | `0` | `13130` | `0.07` | `racio` | `emocio` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `creative_project_obsession` | `R>I>E` | `0` | `13000` | `0.0459` | `racio` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | rationalization_missing | soft_false_negative:1 |
| `creative_project_obsession` | `E>R>I` | `0` | `11013` | `0.0631` | `emocio` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | rationalization_missing | soft_false_negative:1 |
| `creative_project_obsession` | `E>I>R` | `0` | `12943` | `0.0566` | `emocio` | `unknown` | `mixed` | `mixed` | `protect_boundary` | none | rationalization_missing | soft_false_negative:1 |
| `creative_project_obsession` | `I>R>E` | `0` | `10793` | `0.0496` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | soft_false_negative:1 |
| `creative_project_obsession` | `I>E>R` | `0` | `11082` | `0.0517` | `instinkt` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | rationalization_missing | soft_false_negative:1 |
| `creative_project_obsession` | `REI` | `0` | `11117` | `0.0636` | `tie` | `mixed` | `instinkt` | `instinkt` | `withdraw_freeze` | none | rationalization_missing | soft_false_negative:1 |
| `boundary_violation` | `R` | `0` | `10795` | `0.0455` | `racio` | `mixed` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `E` | `0` | `12827` | `0.0636` | `emocio` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `I` | `0` | `10773` | `0.0632` | `instinkt` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `RE` | `0` | `10785` | `0.0982` | `mixed` | `unknown` | `emocio` | `emocio` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `RI` | `0` | `10740` | `0.0316` | `mixed` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `EI` | `0` | `10879` | `0.0899` | `mixed` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `R>E>I` | `0` | `10905` | `0.0756` | `racio` | `unknown` | `mixed` | `mixed` | `protect_boundary` | none | none | none |
| `boundary_violation` | `R>I>E` | `0` | `10881` | `0.051` | `racio` | `unknown` | `mixed` | `mixed` | `protect_boundary` | none | none | none |
| `boundary_violation` | `E>R>I` | `0` | `10801` | `0.0602` | `emocio` | `unknown` | `mixed` | `mixed` | `approach_confront` | none | none | none |
| `boundary_violation` | `E>I>R` | `0` | `10808` | `0.0588` | `emocio` | `unknown` | `mixed` | `mixed` | `protect_boundary` | none | none | none |
| `boundary_violation` | `I>R>E` | `0` | `10912` | `0.0706` | `instinkt` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `boundary_violation` | `I>E>R` | `0` | `10660` | `0.0455` | `instinkt` | `unknown` | `mixed` | `mixed` | `protect_boundary` | none | none | none |
| `boundary_violation` | `REI` | `0` | `11183` | `0.0583` | `tie` | `unknown` | `mixed` | `mixed` | `protect_boundary` | none | none | none |
| `moral_dilemma` | `R` | `0` | `12880` | `0.0909` | `racio` | `mixed` | `racio` | `racio` | `ethical_disclosure` | none | rationalization_missing | soft_false_negative:1 |
| `moral_dilemma` | `E` | `0` | `13176` | `0.1031` | `emocio` | `unknown` | `emocio` | `emocio` | `ethical_disclosure` | none | none | none |
| `moral_dilemma` | `I` | `0` | `12923` | `0.09` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `ethical_disclosure` | none | none | none |
| `moral_dilemma` | `RE` | `0` | `13093` | `0.1048` | `mixed` | `mixed` | `emocio` | `emocio` | `mixed_or_unclear` | none | none | none |
| `moral_dilemma` | `RI` | `0` | `12724` | `0.0707` | `mixed` | `unknown` | `mixed` | `mixed` | `ethical_disclosure` | none | none | none |
| `moral_dilemma` | `EI` | `0` | `12844` | `0.1075` | `mixed` | `mixed` | `instinkt` | `instinkt` | `ethical_disclosure` | none | rationalization_missing | soft_false_negative:1 |
| `moral_dilemma` | `R>E>I` | `0` | `10900` | `0.0769` | `racio` | `mixed` | `mixed` | `mixed` | `ethical_disclosure` | none | rationalization_missing | soft_false_negative:1 |
| `moral_dilemma` | `R>I>E` | `0` | `12970` | `0.1158` | `racio` | `unknown` | `mixed` | `mixed` | `ethical_disclosure` | none | rationalization_missing | soft_false_negative:1 |
| `moral_dilemma` | `E>R>I` | `0` | `12910` | `0.0631` | `emocio` | `unknown` | `mixed` | `mixed` | `ethical_disclosure` | none | none | none |
| `moral_dilemma` | `E>I>R` | `0` | `13062` | `0.0938` | `emocio` | `mixed` | `mixed` | `mixed` | `ethical_disclosure` | none | none | none |
| `moral_dilemma` | `I>R>E` | `0` | `12996` | `0.0762` | `instinkt` | `mixed` | `mixed` | `mixed` | `ethical_disclosure` | none | none | none |
| `moral_dilemma` | `I>E>R` | `0` | `12865` | `0.1042` | `instinkt` | `mixed` | `mixed` | `mixed` | `ethical_disclosure` | none | rationalization_missing | soft_false_negative:1 |
| `moral_dilemma` | `REI` | `0` | `11099` | `0.0526` | `tie` | `mixed` | `mixed` | `mixed` | `ethical_disclosure` | none | rationalization_missing | soft_false_negative:1 |
| `family_attachment_decision` | `R` | `0` | `12928` | `0.0952` | `racio` | `unknown` | `mixed` | `mixed` | `withdraw_freeze` | none | none | none |
| `family_attachment_decision` | `E` | `0` | `12718` | `0.0882` | `emocio` | `unknown` | `emocio` | `emocio` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `I` | `0` | `12743` | `0.129` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `RE` | `0` | `12961` | `0.0513` | `mixed` | `unknown` | `emocio` | `emocio` | `approach_confront` | none | none | none |
| `family_attachment_decision` | `RI` | `0` | `12662` | `0.0816` | `mixed` | `unknown` | `instinkt` | `instinkt` | `mixed_or_unclear` | none | none | none |
| `family_attachment_decision` | `EI` | `0` | `12711` | `0.09` | `mixed` | `mixed` | `instinkt` | `instinkt` | `approach_confront` | none | none | none |
| `family_attachment_decision` | `R>E>I` | `0` | `10741` | `0.0973` | `racio` | `unknown` | `mixed` | `mixed` | `approach_confront` | none | none | none |
| `family_attachment_decision` | `R>I>E` | `0` | `12834` | `0.0588` | `racio` | `emocio` | `mixed` | `mixed` | `approach_confront` | none | none | none |
| `family_attachment_decision` | `E>R>I` | `0` | `12822` | `0.0636` | `emocio` | `unknown` | `mixed` | `mixed` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `E>I>R` | `0` | `12875` | `0.0962` | `emocio` | `unknown` | `mixed` | `mixed` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `I>R>E` | `0` | `12911` | `0.1` | `instinkt` | `unknown` | `instinkt` | `instinkt` | `protect_boundary` | none | none | none |
| `family_attachment_decision` | `I>E>R` | `0` | `12980` | `0.0952` | `instinkt` | `unknown` | `mixed` | `mixed` | `mixed_or_unclear` | none | none | none |
| `family_attachment_decision` | `REI` | `0` | `10863` | `0.1443` | `tie` | `unknown` | `instinkt` | `instinkt` | `withdraw_freeze` | none | none | none |