# REI Role Drift Probe

## Run

- **run_id:** `20260516_083426`
- **provider:** `deterministic`
- **model:** `qwen/qwen3.5-9b`
- **num_ctx:** `65536`
- **num_gpu:** `999`
- **cases:** `1`
- **fallback_count:** `0`
- **average_elapsed_seconds:** `0.001`
- **average_max_signal_jaccard:** `0.0833`
- **average_drift_by_mind:** `{"emocio": 0.0, "instinkt": 0.1429, "racio": 0.2143}`
- **role_drift_flags:** `{"instinkt_uses_rational_strategy_language": 1, "racio_uses_fear_body_or_image_language": 1}`
- **repetition_hits:** `{"bounded test": 3, "minimum safety condition": 2, "one reversible test": 2, "responsible planning": 3, "smallest acceptable exposure": 1, "stop condition": 2, "take only the next reversible step": 1}`

## Case Index

| Scenario | Profile | Expected | Leading | Stability | Drift R/E/I | Max overlap | Integrated decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| material-loss-with-evidence | R=E=I | racio_instinkt | instinkt | fragile | 0.2143/0.0/0.1429 | 0.0833 | Take only the next reversible step and do not treat the explanation as final acceptance. |

## material-loss-with-evidence / R=E=I / repeat 1

**Prompt:** A person suspects that expensive equipment at work may be stolen tonight. They have partial evidence, a limited window to act, and responsibility for the material loss if it happens. They must choose whether to secure the equipment quietly, confront someone, or wait for proof.

### Final Result

- **leading_mind:** instinkt
- **profile_leader:** tie
- **situational_driver:** instinkt
- **resultant_leader_under_pressure:** instinkt
- **racio_role:** rationalizer
- **emocio_role:** shame_driver
- **instinkt_role:** protector
- **decision_stability:** fragile
- **acceptance_level:** mixed
- **behavioral_alignment:** split
- **integrated_decision:** Take only the next reversible step and do not treat the explanation as final acceptance.
- **likely_action_under_pressure:** Delay or reduce exposure while calling it responsible caution.
- **smallest_acceptable_next_step:** Define one reversible test with facts, boundary, and a stop condition.
- **distinctness:** `{"pair_jaccard": {"racio_emocio": 0.0508, "racio_instinkt": 0.0517, "emocio_instinkt": 0.0833}, "max_jaccard": 0.0833, "distinctness_warning": false}`
- **repetition_hits:** `{"one reversible test": 2, "bounded test": 3, "minimum safety condition": 2, "smallest acceptable exposure": 1, "stop condition": 2, "take only the next reversible step": 1, "responsible planning": 3}`

### Racio

- **perception:** The conscious layer sees a situation that needs facts, sequence, constraints, and a reversible next step.
- **primary_motive:** Control uncertainty through explicit structure.
- **preferred_action:** Create a bounded plan and test only the next controllable move.
- **accepted_expression:** It uses analysis as a service to the whole system.
- **non_accepted_expression:** It turns explanation into control and may call fear or desire objective logic.
- **resistance_to_other_minds:** It resists signals that cannot be converted into explicit variables.
- **what_this_mind_needs:** Enough facts, sequence, and feedback to avoid inventing certainty.
- **risk_if_ignored:** The situation can become impulsive, vague, or impossible to execute.
- **risk_if_dominant:** The person may delay, over-control, or rationalize suppression as responsibility.
- **uncertainty:** This is a provisional simulation from limited user input.
- **known_facts:** ["A person suspects that expensive equipment at work may be stolen tonight. They have partial evidence, a limited window to act, and responsibility for the material loss if it happen"]
- **unknowns:** ["explicit option list", "actual body state and real-world constraints"]
- **logical_options:** ["delay until the constraints are clearer", "take one bounded test action", "decline or pause if safety cannot be defined"]
- **timeline_or_sequence:** Name facts, identify unknowns, choose a reversible test, then reassess pressure from the other processors.
- **rationalization_risk:** Planning may become a clean explanation for pressure that comes from image desire or safety fear.
- **role_drift_score:** `0.2143`
- **native_hits:** `{"evidence": 1, "sequence": 2, "option": 1, "control": 3, "material": 1, "loss": 1, "reversible": 2}`
- **foreign_hits:** `{"fear": 2, "body": 1}`
- **flags:** `["racio_uses_fear_body_or_image_language"]`

### Emocio translated

- **perception:** The translated image signal notices whether the scene promises aliveness, recognition, shame, or a deadened self-image.
- **primary_motive:** Protect and renew the desired image of self-in-the-scene.
- **preferred_action:** Move toward one contained expression that restores aliveness without coercion.
- **accepted_expression:** It adds motivation, contact, beauty, and courage without needing to dominate.
- **non_accepted_expression:** It may chase admiration, dramatize injury, or mistake vividness for truth.
- **resistance_to_other_minds:** It resists dry control and protective closure when they make the scene feel lifeless.
- **what_this_mind_needs:** A dignified image of action that includes safety and sequence.
- **risk_if_ignored:** Vitality may turn into resentment, shame, or compensatory image hunger.
- **risk_if_dominant:** The person may act for display before checking costs, boundaries, or truth.
- **uncertainty:** The actual image signal is inferred from text and may be incomplete.
- **current_image:** A person stands before a possible change in how they are seen and how alive the situation feels.
- **desired_image:** Dignity, vividness, response, and the feeling that the self can become more alive.
- **broken_image:** Looking foolish, being unseen, or losing the attractive image of the possible future.
- **social_meaning:** The situation carries a visible meaning about value, courage, belonging, or status.
- **attraction_or_rejection:** It is pulled toward the image that feels alive and away from the image that feels humiliating.
- **pride_or_shame:** Pride wants a scene worth entering; shame fears exposure without recognition.
- **competition_signal:** A mild pressure appears to prove value or avoid being surpassed.
- **attack_impulse:** If humiliated, the pressure could turn into sharp defensiveness rather than clean expression.
- **role_drift_score:** `0.0`
- **native_hits:** `{"image": 10, "alive": 3, "admiration": 1, "shame": 3, "pride": 1, "visible": 1, "beauty": 1, "recognition": 2, "desire": 1, "scene": 4, "status": 1}`
- **foreign_hits:** `{}`
- **flags:** `[]`

### Instinkt translated

- **perception:** The translated protective signal scans for exposure, loss, instability, boundary breach, and irreversible consequence.
- **primary_motive:** Preserve safety, boundary, attachment, and future recoverability.
- **preferred_action:** Pause long enough to define the minimum safety condition before opening further.
- **accepted_expression:** It protects without imprisoning the system.
- **non_accepted_expression:** It may treat discomfort as proof of danger and block every opening.
- **resistance_to_other_minds:** It resists vivid desire and abstract plans when they increase exposure too quickly.
- **what_this_mind_needs:** A concrete boundary, low exposure, and a way back.
- **risk_if_ignored:** Fear may return as sabotage, withdrawal, or panic after action begins.
- **risk_if_dominant:** The person may call avoidance safety and never test reality.
- **uncertainty:** The protective signal is inferred from limited text, not from direct bodily data.
- **threat_map:** Loss of safety, resources, trust, reputation, or future room to maneuver.
- **loss_map:** The feared loss is stability, attachment, dignity, or the ability to recover if the move fails.
- **body_alarm:** A general stop-check signal is present; this is not medical evidence or diagnosis.
- **boundary_issue:** The boundary is unclear until the next step is reversible and consent-safe.
- **trust_issue:** Trust requires evidence that the situation will not demand more exposure than promised.
- **attachment_issue:** Attachment pressure may increase if the choice risks closeness, belonging, or continuity.
- **scarcity_signal:** Scarcity appears around time, money, energy, attention, or safe options.
- **flight_or_freeze_signal:** The protective pressure may delay or narrow the field until safety is named.
- **minimum_safety_condition:** Define one reversible test, a stop condition, and the smallest acceptable exposure.
- **role_drift_score:** `0.1429`
- **native_hits:** `{"danger": 1, "boundary": 4, "loss": 3, "exposure": 5, "stop": 2, "scarcity": 1, "trust": 2}`
- **foreign_hits:** `{"evidence": 2, "data": 1}`
- **flags:** `["instinkt_uses_rational_strategy_language"]`

### Acceptance

- **overall_level:** mixed
- **racio_acceptance:** Racio can contribute if its plan remains provisional and checks non-verbal resistance.
- **emocio_acceptance:** Emocio can contribute if image, desire, and shame are named without turning into domination.
- **instinkt_acceptance:** Instinkt can contribute if safety is defined as a condition for action, not a veto on all movement.
- **main_conflict:** Racio can explain a plan, while Emocio and Instinkt do not yet accept its cost.
- **likely_sabotage_point:** The system may delay or reframe avoidance as responsible planning.
- **task_delegation:** {"lead_next": "racio", "racio_needs": "clear facts, unknowns, sequence, and a bounded test", "emocio_needs": "an image of aliveness or dignity that does not require manipulation", "instinkt_needs": "minimum safety, boundary, and reversibility", "racio_action_tag": "delay", "emocio_action_tag": "move", "instinkt_action_tag": "delay"}
- **behavioral_alignment:** split
- **acceptance_quality:** mixed
- **non_acceptance_pattern:** rationalized safety freeze
- **coalition_pattern:** Instinkt + Racio coalition: safety fear translated as responsible planning.
- **sabotage_mechanism:** The system may delay or reframe avoidance as responsible planning.

## Output Files

- **summary:** `output\reports\rei_dashboard_smoke_no_llm\summary.json`
- **plan:** `output\reports\rei_dashboard_smoke_no_llm\scenario_plan.json`
- **results_jsonl:** `output\reports\rei_dashboard_smoke_no_llm\results.jsonl`
- **report:** `output\reports\rei_dashboard_smoke_no_llm\report.md`
- **progress:** `output\reports\rei_dashboard_smoke_no_llm\progress.log`