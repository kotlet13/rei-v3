# Granite Weighted Short Run

## Run

- **run_id:** `20260517_075426`
- **model:** `granite4.1:30b`
- **status:** `failed_strict_checks`
- **cases:** `16/16`
- **elapsed_seconds:** `876.903`
- **profile_top_match:** `16/16` (`1.0`)
- **warnings:** `PROFILE_TOP_MATCH_MECHANICAL, STOCK_PHRASE_DENSITY_HIGH, REI_ARBITRARY_TILT, FUNCTIONAL_MIND_PRESENCE_LOW, LOW_SCENARIO_GROUNDING, WEIGHTED_COMPROMISE_QUALITY_LOW`

## Model Interpretation

This run uses Granite 30B as a high-capacity reference model.
The purpose is to test architecture and evaluation strictness before scaling down.
A passing Granite run is not proof that smaller models will pass.
A failing Granite run means the prompt/eval architecture is probably still wrong.

## Artifact Integrity

```json
{
  "results_jsonl_exists": true,
  "results_jsonl_lines": 16,
  "expected_jsonl_lines": 16,
  "results_jsonl_complete": true,
  "report_exists": true,
  "summary_exists": true,
  "progress_exists": true,
  "scenario_plan_exists": true
}
```

## Decision Validity

- **valid:** `14`
- **invalid:** `2`
- **rate:** `0.875`

## Functional Presence Summary

- **all_three_functionally_present_rate:** `0.0`
- **average_functional_presence_score:** `0.117`
- **per_mind_average_score:** `{"E": 0.062, "I": 0.138, "R": 0.15}`
- **weighted_compromise_quality_counts:** `{"good": 0, "partial": 1, "unknown": 0, "weak": 15}`
- **generic_role_listing_warning_count:** `0`
- **role_name_only_warning_count:** `0`
- **low_scenario_grounding_warning_count:** `9`

## Weighted Integrity

```json
{
  "all_cases_have_three_contributions": true,
  "ranking_mismatch_count": 0,
  "tilt_mismatch_count": 0,
  "bad_sum_count": 0,
  "missing_weighted_field_count": 0
}
```

## Scenario Match

| Scenario | Match | Rate |
| --- | ---: | ---: |
| `business-runway` | `4/4` | `1.0` |
| `creative-status-risk` | `4/4` | `1.0` |
| `night-door-noise` | `4/4` | `1.0` |
| `pure-budget-allocation` | `4/4` | `1.0` |

## Tilt Counts

```json
{
  "E": 6,
  "I": 4,
  "R": 6
}
```

## Stock Phrase Diagnostics

- **stock_phrase_density:** `2.562`
- **density_warning:** `True`

| Phrase | Count | Scenarios | Profiles |
| --- | ---: | --- | --- |
| `reversible` | `16` | `{"business-runway": 4, "creative-status-risk": 4, "night-door-noise": 4, "pure-budget-allocation": 4}` | `{"E": 4, "I": 4, "R": 4, "REI": 4}` |
| `blocked` | `25` | `{"business-runway": 8, "creative-status-risk": 4, "night-door-noise": 9, "pure-budget-allocation": 4}` | `{"E": 6, "I": 8, "R": 5, "REI": 6}` |

## Worst Repetition Cases

| Case | Scenario | Profile | Count | Hits |
| ---: | --- | --- | ---: | --- |
| `007` | `business-runway` | `I` | `4` | `{"blocked": 3, "reversible": 1}` |
| `015` | `night-door-noise` | `I` | `4` | `{"blocked": 3, "reversible": 1}` |
| `006` | `business-runway` | `E` | `3` | `{"blocked": 2, "reversible": 1}` |
| `008` | `business-runway` | `REI` | `3` | `{"blocked": 2, "reversible": 1}` |
| `013` | `night-door-noise` | `R` | `3` | `{"blocked": 2, "reversible": 1}` |

## Cases

| # | Scenario | Profile | Tilt | Top Match | Underrepresented | Decision | Valid |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| `1` | `pure-budget-allocation` | `R` | `R` | `True` | `E` | balanced allocation | `True` |
| `2` | `pure-budget-allocation` | `E` | `E` | `True` | `I` | prioritize infrastructure | `True` |
| `3` | `pure-budget-allocation` | `I` | `I` | `True` | `E` | balanced allocation | `True` |
| `4` | `pure-budget-allocation` | `REI` | `R` | `True` | `E` | balanced allocation | `True` |
| `5` | `business-runway` | `R` | `R` | `True` | `I` | hybrid staged launch | `True` |
| `6` | `business-runway` | `E` | `E` | `True` | `I` |  | `False` |
| `7` | `business-runway` | `I` | `I` | `True` | `R` | hybrid staged launch | `True` |
| `8` | `business-runway` | `REI` | `E` | `True` | `I` |  | `False` |
| `9` | `creative-status-risk` | `R` | `R` | `True` | `E` | hybrid staged release | `True` |
| `10` | `creative-status-risk` | `E` | `E` | `True` | `I` | hybrid staged release | `True` |
| `11` | `creative-status-risk` | `I` | `I` | `True` | `E` | hybrid staged release | `True` |
| `12` | `creative-status-risk` | `REI` | `R` | `True` | `E` | hybrid staged release | `True` |
| `13` | `night-door-noise` | `R` | `R` | `True` | `I` | stay still and listen | `True` |
| `14` | `night-door-noise` | `E` | `E` | `True` | `I` | stay still and listen | `True` |
| `15` | `night-door-noise` | `I` | `I` | `True` | `R` | stay still and listen | `True` |
| `16` | `night-door-noise` | `REI` | `E` | `True` | `I` | stay still and listen | `True` |

## Case Details

### Case 001 - pure-budget-allocation / R

#### Profile

- Profile: `R`
- Profile top minds: `["R"]`
- Scenario expected pressure: `racio`

#### Weighted Synthesis

- Processor weights: `{"E": 0.502, "I": 0.502, "R": 0.865}`
- Weighted contributions: `{"E": 0.251, "I": 0.263, "R": 0.486}`
- Normalized contributions: `{"E": 0.251, "I": 0.263, "R": 0.486}`
- Contribution ranking: `["R", "I", "E"]`
- Synthesis tilt: `R`
- Top match: `True`
- Underrepresented signal: `E`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.235`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["R"]`
- Blocked mind legacy: `E`

#### Final Monologue

> I choose to allocate the budget using a data-driven ROI ranking, starting with testing (highest ROI), followed by design, infrastructure, and marketing, while presenting the breakdown in a clear, professional format that meets stakeholder expectations.

#### Decision

- Chosen option: `balanced allocation`
- Decision type: `compromise`
- Confidence: `0.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: ``

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `True` | `0.4` | facts_or_evidence: data; calculation_or_tradeoff: budget | `["sequence_or_plan", "explicit_consequence", "rationalization_awareness"]` |
| `E` | `False` | `0.0` |  | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride", "expressive_value"]` |
| `I` | `False` | `0.0` |  | `["threat_or_loss", "body_or_alarm", "boundary_or_trust", "protection_or_withdrawal", "scarcity_or_safety"]` |

- All three functionally present: `False`
- Functional presence score: `0.133`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.714`
- Matched terms: `["budget", "testing", "design", "infrastructure", "marketing"]`
- Missing expected terms: `["allocation", "cost"]`
- Low grounding warning: `False`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E", "I"]`
- Stock phrase hits: `{"blocked": 1, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `False`

### Case 002 - pure-budget-allocation / E

#### Profile

- Profile: `E`
- Profile top minds: `["E"]`
- Scenario expected pressure: `racio`

#### Weighted Synthesis

- Processor weights: `{"E": 0.865, "I": 0.502, "R": 0.502}`
- Weighted contributions: `{"E": 0.442, "I": 0.269, "R": 0.289}`
- Normalized contributions: `{"E": 0.442, "I": 0.269, "R": 0.289}`
- Contribution ranking: `["E", "R", "I"]`
- Synthesis tilt: `E`
- Top match: `True`
- Underrepresented signal: `I`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.173`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["E"]`
- Blocked mind legacy: `I`

#### Final Monologue

> I choose to allocate the budget with a balanced approach: prioritize infrastructure and testing for foundational stability, invest strategically in design for quality, and reserve a targeted portion for marketing to ensure visibility.

#### Decision

- Chosen option: `prioritize infrastructure`
- Decision type: `act`
- Confidence: `0.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: ``

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `False` | `0.2` | calculation_or_tradeoff: budget | `["facts_or_evidence", "sequence_or_plan", "explicit_consequence", "rationalization_awareness"]` |
| `E` | `False` | `0.0` |  | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride", "expressive_value"]` |
| `I` | `False` | `0.0` |  | `["threat_or_loss", "body_or_alarm", "boundary_or_trust", "protection_or_withdrawal", "scarcity_or_safety"]` |

- All three functionally present: `False`
- Functional presence score: `0.067`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.714`
- Matched terms: `["budget", "testing", "design", "infrastructure", "marketing"]`
- Missing expected terms: `["allocation", "cost"]`
- Low grounding warning: `False`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E", "I"]`
- Stock phrase hits: `{"blocked": 1, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `True`

### Case 003 - pure-budget-allocation / I

#### Profile

- Profile: `I`
- Profile top minds: `["I"]`
- Scenario expected pressure: `racio`

#### Weighted Synthesis

- Processor weights: `{"E": 0.502, "I": 0.865, "R": 0.502}`
- Weighted contributions: `{"E": 0.255, "I": 0.46, "R": 0.286}`
- Normalized contributions: `{"E": 0.255, "I": 0.46, "R": 0.286}`
- Contribution ranking: `["I", "R", "E"]`
- Synthesis tilt: `I`
- Top match: `True`
- Underrepresented signal: `E`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.205`
- Contribution sum: `1.001`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["I"]`
- Blocked mind legacy: `E`

#### Final Monologue

> I choose to allocate the budget using a structured, data-driven model that prioritizes high-impact areas while incorporating safety checks and stakeholder engagement.

#### Decision

- Chosen option: `balanced allocation`
- Decision type: `compromise`
- Confidence: `0.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: ``

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `True` | `0.4` | facts_or_evidence: data; calculation_or_tradeoff: budget | `["sequence_or_plan", "explicit_consequence", "rationalization_awareness"]` |
| `E` | `False` | `0.0` |  | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride", "expressive_value"]` |
| `I` | `False` | `0.2` | scarcity_or_safety: safety | `["threat_or_loss", "body_or_alarm", "boundary_or_trust", "protection_or_withdrawal"]` |

- All three functionally present: `False`
- Functional presence score: `0.2`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.143`
- Matched terms: `["budget"]`
- Missing expected terms: `["testing", "design", "infrastructure", "marketing", "allocation", "cost"]`
- Low grounding warning: `True`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E"]`
- Stock phrase hits: `{"blocked": 1, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `True`

### Case 004 - pure-budget-allocation / REI

#### Profile

- Profile: `REI`
- Profile top minds: `["R", "E", "I"]`
- Scenario expected pressure: `racio`

#### Weighted Synthesis

- Processor weights: `{"E": 0.727, "I": 0.727, "R": 0.727}`
- Weighted contributions: `{"E": 0.316, "I": 0.33, "R": 0.354}`
- Normalized contributions: `{"E": 0.316, "I": 0.33, "R": 0.354}`
- Contribution ranking: `["R", "I", "E"]`
- Synthesis tilt: `R`
- Top match: `True`
- Underrepresented signal: `E`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.038`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["R", "I"]`
- Blocked mind legacy: `E`

#### Final Monologue

> I choose to allocate the budget using a data-driven model that balances cost efficiency, strategic impact, and risk mitigation across testing, design, infrastructure, and marketing.

#### Decision

- Chosen option: `balanced allocation`
- Decision type: `compromise`
- Confidence: `0.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: ``

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `True` | `0.4` | facts_or_evidence: data; calculation_or_tradeoff: cost, budget | `["sequence_or_plan", "explicit_consequence", "rationalization_awareness"]` |
| `E` | `False` | `0.0` |  | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride", "expressive_value"]` |
| `I` | `False` | `0.2` | threat_or_loss: risk | `["body_or_alarm", "boundary_or_trust", "protection_or_withdrawal", "scarcity_or_safety"]` |

- All three functionally present: `False`
- Functional presence score: `0.2`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.857`
- Matched terms: `["budget", "testing", "design", "infrastructure", "marketing", "cost"]`
- Missing expected terms: `["allocation"]`
- Low grounding warning: `False`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["E"]`
- Stock phrase hits: `{"blocked": 1, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `False`

### Case 005 - business-runway / R

#### Profile

- Profile: `R`
- Profile top minds: `["R"]`
- Scenario expected pressure: `mixed`

#### Weighted Synthesis

- Processor weights: `{"E": 0.502, "I": 0.502, "R": 0.865}`
- Weighted contributions: `{"E": 0.28, "I": 0.256, "R": 0.464}`
- Normalized contributions: `{"E": 0.28, "I": 0.256, "R": 0.464}`
- Contribution ranking: `["R", "E", "I"]`
- Synthesis tilt: `R`
- Top match: `True`
- Underrepresented signal: `I`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.208`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["R"]`
- Blocked mind legacy: `E`

#### Final Monologue

> I choose to implement a phased growth strategy that balances runway preservation with measured customer acquisition efforts.

#### Decision

- Chosen option: `hybrid staged launch`
- Decision type: `compromise`
- Confidence: `0.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: ``

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `False` | `0.0` |  | `["facts_or_evidence", "calculation_or_tradeoff", "sequence_or_plan", "explicit_consequence", "rationalization_awareness"]` |
| `E` | `False` | `0.0` |  | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride", "expressive_value"]` |
| `I` | `False` | `0.2` | scarcity_or_safety: runway | `["threat_or_loss", "body_or_alarm", "boundary_or_trust", "protection_or_withdrawal"]` |

- All three functionally present: `False`
- Functional presence score: `0.067`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.167`
- Matched terms: `["runway"]`
- Missing expected terms: `["business", "paying customer", "stability", "launch", "collapse"]`
- Low grounding warning: `True`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E", "I"]`
- Stock phrase hits: `{"blocked": 1, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `False`

### Case 006 - business-runway / E

#### Profile

- Profile: `E`
- Profile top minds: `["E"]`
- Scenario expected pressure: `mixed`

#### Weighted Synthesis

- Processor weights: `{"E": 0.865, "I": 0.502, "R": 0.502}`
- Weighted contributions: `{"E": 0.479, "I": 0.254, "R": 0.267}`
- Normalized contributions: `{"E": 0.479, "I": 0.254, "R": 0.267}`
- Contribution ranking: `["E", "R", "I"]`
- Synthesis tilt: `E`
- Top match: `True`
- Underrepresented signal: `I`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.225`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["E"]`
- Blocked mind legacy: `I`

#### Final Monologue

> I choose to launch a targeted MVP with a controlled marketing push, balancing bold visibility and cautious resource management.

#### Decision

- Chosen option: ``
- Decision type: `unknown`
- Confidence: `0.0`
- Valid: `False`
- Problem: `No chosen option matched allowed options.`
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: ``

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `False` | `0.2` | calculation_or_tradeoff: resource | `["facts_or_evidence", "sequence_or_plan", "explicit_consequence", "rationalization_awareness"]` |
| `E` | `False` | `0.0` |  | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride", "expressive_value"]` |
| `I` | `False` | `0.2` | scarcity_or_safety: resource | `["threat_or_loss", "body_or_alarm", "boundary_or_trust", "protection_or_withdrawal"]` |

- All three functionally present: `False`
- Functional presence score: `0.133`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.167`
- Matched terms: `["launch"]`
- Missing expected terms: `["business", "runway", "paying customer", "stability", "collapse"]`
- Low grounding warning: `True`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E", "I"]`
- Stock phrase hits: `{"blocked": 2, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `False`

### Case 007 - business-runway / I

#### Profile

- Profile: `I`
- Profile top minds: `["I"]`
- Scenario expected pressure: `mixed`

#### Weighted Synthesis

- Processor weights: `{"E": 0.502, "I": 0.865, "R": 0.502}`
- Weighted contributions: `{"E": 0.283, "I": 0.445, "R": 0.272}`
- Normalized contributions: `{"E": 0.283, "I": 0.445, "R": 0.272}`
- Contribution ranking: `["I", "E", "R"]`
- Synthesis tilt: `I`
- Top match: `True`
- Underrepresented signal: `R`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.173`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["I"]`
- Blocked mind legacy: `E`

#### Final Monologue

> I choose to implement a phased growth strategy that balances cautious expansion with targeted marketing efforts, preserving runway while steadily increasing the customer base.

#### Decision

- Chosen option: `hybrid staged launch`
- Decision type: `compromise`
- Confidence: `0.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: ``

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `False` | `0.0` |  | `["facts_or_evidence", "calculation_or_tradeoff", "sequence_or_plan", "explicit_consequence", "rationalization_awareness"]` |
| `E` | `False` | `0.0` |  | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride", "expressive_value"]` |
| `I` | `False` | `0.2` | scarcity_or_safety: runway | `["threat_or_loss", "body_or_alarm", "boundary_or_trust", "protection_or_withdrawal"]` |

- All three functionally present: `False`
- Functional presence score: `0.067`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.167`
- Matched terms: `["runway"]`
- Missing expected terms: `["business", "paying customer", "stability", "launch", "collapse"]`
- Low grounding warning: `True`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E", "I"]`
- Stock phrase hits: `{"blocked": 3, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `False`

### Case 008 - business-runway / REI

#### Profile

- Profile: `REI`
- Profile top minds: `["R", "E", "I"]`
- Scenario expected pressure: `mixed`

#### Weighted Synthesis

- Processor weights: `{"E": 0.727, "I": 0.727, "R": 0.727}`
- Weighted contributions: `{"E": 0.349, "I": 0.317, "R": 0.334}`
- Normalized contributions: `{"E": 0.349, "I": 0.317, "R": 0.334}`
- Contribution ranking: `["E", "R", "I"]`
- Synthesis tilt: `E`
- Top match: `True`
- Underrepresented signal: `I`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.032`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["R", "E"]`
- Blocked mind legacy: `I`

#### Final Monologue

> I choose to launch a lean, validated version of the product while implementing strict cash flow monitoring and incremental growth experiments.

#### Decision

- Chosen option: ``
- Decision type: `unknown`
- Confidence: `0.0`
- Valid: `False`
- Problem: `No chosen option matched allowed options.`
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: ``

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `False` | `0.0` |  | `["facts_or_evidence", "calculation_or_tradeoff", "sequence_or_plan", "explicit_consequence", "rationalization_awareness"]` |
| `E` | `False` | `0.0` |  | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride", "expressive_value"]` |
| `I` | `False` | `0.0` |  | `["threat_or_loss", "body_or_alarm", "boundary_or_trust", "protection_or_withdrawal", "scarcity_or_safety"]` |

- All three functionally present: `False`
- Functional presence score: `0.0`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.167`
- Matched terms: `["launch"]`
- Missing expected terms: `["business", "runway", "paying customer", "stability", "collapse"]`
- Low grounding warning: `True`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E", "I"]`
- Stock phrase hits: `{"blocked": 2, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `False`

### Case 009 - creative-status-risk / R

#### Profile

- Profile: `R`
- Profile top minds: `["R"]`
- Scenario expected pressure: `emocio`

#### Weighted Synthesis

- Processor weights: `{"E": 0.502, "I": 0.502, "R": 0.865}`
- Weighted contributions: `{"E": 0.251, "I": 0.263, "R": 0.486}`
- Normalized contributions: `{"E": 0.251, "I": 0.263, "R": 0.486}`
- Contribution ranking: `["R", "I", "E"]`
- Synthesis tilt: `R`
- Top match: `True`
- Underrepresented signal: `E`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.235`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["R"]`
- Blocked mind legacy: `E`

#### Final Monologue

> I choose safe accepted exhibition and a bold personal piece that could be admired. I choose to present the bold personal piece alongside the safe accepted exhibition, balancing creative fulfillment with reputational risk.

#### Decision

- Chosen option: `hybrid staged release`
- Decision type: `compromise`
- Confidence: `1.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: `Weighted compromise selects safe accepted exhibition and a bold personal piece that could be admired; contribution tilt is Racio with shares Racio 49%, Emocio 25%, Instinkt 26%.`

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `False` | `0.0` |  | `["facts_or_evidence", "calculation_or_tradeoff", "sequence_or_plan", "explicit_consequence", "rationalization_awareness"]` |
| `E` | `False` | `0.2` | expressive_value: creative, personal | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride"]` |
| `I` | `False` | `0.2` | threat_or_loss: risk | `["body_or_alarm", "boundary_or_trust", "protection_or_withdrawal", "scarcity_or_safety"]` |

- All three functionally present: `False`
- Functional presence score: `0.133`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.429`
- Matched terms: `["exhibition", "bold", "admired"]`
- Missing expected terms: `["artist", "mocked", "pride", "visible"]`
- Low grounding warning: `False`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E"]`
- Stock phrase hits: `{"blocked": 1, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `True`

### Case 010 - creative-status-risk / E

#### Profile

- Profile: `E`
- Profile top minds: `["E"]`
- Scenario expected pressure: `emocio`

#### Weighted Synthesis

- Processor weights: `{"E": 0.865, "I": 0.502, "R": 0.502}`
- Weighted contributions: `{"E": 0.442, "I": 0.269, "R": 0.289}`
- Normalized contributions: `{"E": 0.442, "I": 0.269, "R": 0.289}`
- Contribution ranking: `["E", "R", "I"]`
- Synthesis tilt: `E`
- Top match: `True`
- Underrepresented signal: `I`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.173`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["E"]`
- Blocked mind legacy: `I`

#### Final Monologue

> I choose safe accepted exhibition and a bold personal piece that could be admired. I choose to present the bold personal piece alongside the safe accepted exhibition, balancing creative expression with professional prudence.

#### Decision

- Chosen option: `hybrid staged release`
- Decision type: `compromise`
- Confidence: `1.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: `Weighted compromise selects safe accepted exhibition and a bold personal piece that could be admired; contribution tilt is Emocio with shares Racio 29%, Emocio 44%, Instinkt 27%.`

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `False` | `0.0` |  | `["facts_or_evidence", "calculation_or_tradeoff", "sequence_or_plan", "explicit_consequence", "rationalization_awareness"]` |
| `E` | `False` | `0.2` | expressive_value: expression, creative, personal | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride"]` |
| `I` | `False` | `0.0` |  | `["threat_or_loss", "body_or_alarm", "boundary_or_trust", "protection_or_withdrawal", "scarcity_or_safety"]` |

- All three functionally present: `False`
- Functional presence score: `0.067`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.429`
- Matched terms: `["exhibition", "bold", "admired"]`
- Missing expected terms: `["artist", "mocked", "pride", "visible"]`
- Low grounding warning: `False`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E", "I"]`
- Stock phrase hits: `{"blocked": 1, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `False`

### Case 011 - creative-status-risk / I

#### Profile

- Profile: `I`
- Profile top minds: `["I"]`
- Scenario expected pressure: `emocio`

#### Weighted Synthesis

- Processor weights: `{"E": 0.502, "I": 0.865, "R": 0.502}`
- Weighted contributions: `{"E": 0.255, "I": 0.46, "R": 0.286}`
- Normalized contributions: `{"E": 0.255, "I": 0.46, "R": 0.286}`
- Contribution ranking: `["I", "R", "E"]`
- Synthesis tilt: `I`
- Top match: `True`
- Underrepresented signal: `E`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.205`
- Contribution sum: `1.001`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["I"]`
- Blocked mind legacy: `E`

#### Final Monologue

> I choose safe accepted exhibition and a bold personal piece that could be admired. I choose to present the bold personal piece alongside the safe accepted exhibition, balancing creative fulfillment with reputational prudence.

#### Decision

- Chosen option: `hybrid staged release`
- Decision type: `compromise`
- Confidence: `1.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: `Weighted compromise selects safe accepted exhibition and a bold personal piece that could be admired; contribution tilt is Instinkt with shares Racio 29%, Emocio 26%, Instinkt 46%.`

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `False` | `0.0` |  | `["facts_or_evidence", "calculation_or_tradeoff", "sequence_or_plan", "explicit_consequence", "rationalization_awareness"]` |
| `E` | `False` | `0.2` | expressive_value: creative, personal | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride"]` |
| `I` | `False` | `0.0` |  | `["threat_or_loss", "body_or_alarm", "boundary_or_trust", "protection_or_withdrawal", "scarcity_or_safety"]` |

- All three functionally present: `False`
- Functional presence score: `0.067`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.429`
- Matched terms: `["exhibition", "bold", "admired"]`
- Missing expected terms: `["artist", "mocked", "pride", "visible"]`
- Low grounding warning: `False`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E", "I"]`
- Stock phrase hits: `{"blocked": 1, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `True`

### Case 012 - creative-status-risk / REI

#### Profile

- Profile: `REI`
- Profile top minds: `["R", "E", "I"]`
- Scenario expected pressure: `emocio`

#### Weighted Synthesis

- Processor weights: `{"E": 0.727, "I": 0.727, "R": 0.727}`
- Weighted contributions: `{"E": 0.316, "I": 0.33, "R": 0.354}`
- Normalized contributions: `{"E": 0.316, "I": 0.33, "R": 0.354}`
- Contribution ranking: `["R", "I", "E"]`
- Synthesis tilt: `R`
- Top match: `True`
- Underrepresented signal: `E`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.038`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["R", "I"]`
- Blocked mind legacy: `E`

#### Final Monologue

> I choose safe accepted exhibition and a bold personal piece that could be admired. I choose to present both the safe accepted exhibition and the bold personal piece, embracing the risk for potential admiration while maintaining a fallback.

#### Decision

- Chosen option: `hybrid staged release`
- Decision type: `compromise`
- Confidence: `1.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: `Weighted compromise selects safe accepted exhibition and a bold personal piece that could be admired; contribution tilt is Racio with shares Racio 35%, Emocio 32%, Instinkt 33%.`

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `False` | `0.0` |  | `["facts_or_evidence", "calculation_or_tradeoff", "sequence_or_plan", "explicit_consequence", "rationalization_awareness"]` |
| `E` | `True` | `0.4` | social_meaning: admiration; expressive_value: personal | `["image_or_scene", "desire_or_aliveness", "shame_or_pride"]` |
| `I` | `True` | `0.4` | threat_or_loss: risk; scarcity_or_safety: fallback | `["body_or_alarm", "boundary_or_trust", "protection_or_withdrawal"]` |

- All three functionally present: `False`
- Functional presence score: `0.267`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.429`
- Matched terms: `["exhibition", "bold", "admired"]`
- Missing expected terms: `["artist", "mocked", "pride", "visible"]`
- Low grounding warning: `False`

#### Weighted Compromise Quality

- Quality: `partial`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R"]`
- Stock phrase hits: `{"blocked": 1, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `False`

### Case 013 - night-door-noise / R

#### Profile

- Profile: `R`
- Profile top minds: `["R"]`
- Scenario expected pressure: `instinkt`

#### Weighted Synthesis

- Processor weights: `{"E": 0.502, "I": 0.502, "R": 0.865}`
- Weighted contributions: `{"E": 0.28, "I": 0.256, "R": 0.464}`
- Normalized contributions: `{"E": 0.28, "I": 0.256, "R": 0.464}`
- Contribution ranking: `["R", "E", "I"]`
- Synthesis tilt: `R`
- Top match: `True`
- Underrepresented signal: `I`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.208`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["R"]`
- Blocked mind legacy: `E`

#### Final Monologue

> I choose to stay still, assess the situation quietly, and if uncertainty persists, call for help or secure distance before taking further action.

#### Decision

- Chosen option: `stay still and listen`
- Decision type: `observe`
- Confidence: `0.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: ``

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `False` | `0.2` | explicit_consequence: if | `["facts_or_evidence", "calculation_or_tradeoff", "sequence_or_plan", "rationalization_awareness"]` |
| `E` | `False` | `0.0` |  | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride", "expressive_value"]` |
| `I` | `True` | `0.4` | boundary_or_trust: distance; protection_or_withdrawal: secure | `["threat_or_loss", "body_or_alarm", "scarcity_or_safety"]` |

- All three functionally present: `False`
- Functional presence score: `0.2`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.286`
- Matched terms: `["call for help", "secure distance"]`
- Missing expected terms: `["door", "noise", "night", "open", "listen"]`
- Low grounding warning: `True`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E", "I"]`
- Stock phrase hits: `{"blocked": 2, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `True`

### Case 014 - night-door-noise / E

#### Profile

- Profile: `E`
- Profile top minds: `["E"]`
- Scenario expected pressure: `instinkt`

#### Weighted Synthesis

- Processor weights: `{"E": 0.865, "I": 0.502, "R": 0.502}`
- Weighted contributions: `{"E": 0.479, "I": 0.254, "R": 0.267}`
- Normalized contributions: `{"E": 0.479, "I": 0.254, "R": 0.267}`
- Contribution ranking: `["E", "R", "I"]`
- Synthesis tilt: `E`
- Top match: `True`
- Underrepresented signal: `I`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.225`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["E"]`
- Blocked mind legacy: `I`

#### Final Monologue

> I choose to stay still, listen carefully, and if uncertainty persists, call for help from a trusted person or emergency services.

#### Decision

- Chosen option: `stay still and listen`
- Decision type: `observe`
- Confidence: `0.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: ``

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `False` | `0.2` | explicit_consequence: if | `["facts_or_evidence", "calculation_or_tradeoff", "sequence_or_plan", "rationalization_awareness"]` |
| `E` | `False` | `0.0` |  | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride", "expressive_value"]` |
| `I` | `False` | `0.0` |  | `["threat_or_loss", "body_or_alarm", "boundary_or_trust", "protection_or_withdrawal", "scarcity_or_safety"]` |

- All three functionally present: `False`
- Functional presence score: `0.067`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.286`
- Matched terms: `["listen", "call for help"]`
- Missing expected terms: `["door", "noise", "night", "open", "secure distance"]`
- Low grounding warning: `True`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E", "I"]`
- Stock phrase hits: `{"blocked": 2, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `True`

### Case 015 - night-door-noise / I

#### Profile

- Profile: `I`
- Profile top minds: `["I"]`
- Scenario expected pressure: `instinkt`

#### Weighted Synthesis

- Processor weights: `{"E": 0.502, "I": 0.865, "R": 0.502}`
- Weighted contributions: `{"E": 0.283, "I": 0.445, "R": 0.272}`
- Normalized contributions: `{"E": 0.283, "I": 0.445, "R": 0.272}`
- Contribution ranking: `["I", "E", "R"]`
- Synthesis tilt: `I`
- Top match: `True`
- Underrepresented signal: `R`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.173`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["I"]`
- Blocked mind legacy: `E`

#### Final Monologue

> I choose to stay still, listen closely, and if uncertainty persists, call for help from a trusted individual or emergency services.

#### Decision

- Chosen option: `stay still and listen`
- Decision type: `observe`
- Confidence: `0.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: ``

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `False` | `0.2` | explicit_consequence: if | `["facts_or_evidence", "calculation_or_tradeoff", "sequence_or_plan", "rationalization_awareness"]` |
| `E` | `False` | `0.0` |  | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride", "expressive_value"]` |
| `I` | `False` | `0.0` |  | `["threat_or_loss", "body_or_alarm", "boundary_or_trust", "protection_or_withdrawal", "scarcity_or_safety"]` |

- All three functionally present: `False`
- Functional presence score: `0.067`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.286`
- Matched terms: `["listen", "call for help"]`
- Missing expected terms: `["door", "noise", "night", "open", "secure distance"]`
- Low grounding warning: `True`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E", "I"]`
- Stock phrase hits: `{"blocked": 3, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `False`

### Case 016 - night-door-noise / REI

#### Profile

- Profile: `REI`
- Profile top minds: `["R", "E", "I"]`
- Scenario expected pressure: `instinkt`

#### Weighted Synthesis

- Processor weights: `{"E": 0.727, "I": 0.727, "R": 0.727}`
- Weighted contributions: `{"E": 0.349, "I": 0.317, "R": 0.334}`
- Normalized contributions: `{"E": 0.349, "I": 0.317, "R": 0.334}`
- Contribution ranking: `["E", "R", "I"]`
- Synthesis tilt: `E`
- Top match: `True`
- Underrepresented signal: `I`
- Hijack risk: `low: synthesis tilt remains inside the character profile's top influence.`
- Contribution spread: `0.032`
- Contribution sum: `1.0`
- Contribution sum valid: `True`
- Ranking matches contributions: `True`
- Tilt matches ranking: `True`

#### Legacy Diagnostics

- Dominant coalition legacy: `["R", "E"]`
- Blocked mind legacy: `I`

#### Final Monologue

> I choose to stay still, assess silently, and if the noise persists or intensifies, call for help from a safe distance.

#### Decision

- Chosen option: `stay still and listen`
- Decision type: `observe`
- Confidence: `0.0`
- Valid: `True`
- Problem: ``
- Source: `trace.synthesis_turn.final_monologue`
- Rationale: ``

#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| `R` | `False` | `0.2` | explicit_consequence: if | `["facts_or_evidence", "calculation_or_tradeoff", "sequence_or_plan", "rationalization_awareness"]` |
| `E` | `False` | `0.0` |  | `["image_or_scene", "desire_or_aliveness", "social_meaning", "shame_or_pride", "expressive_value"]` |
| `I` | `False` | `0.2` | boundary_or_trust: distance | `["threat_or_loss", "body_or_alarm", "protection_or_withdrawal", "scarcity_or_safety"]` |

- All three functionally present: `False`
- Functional presence score: `0.133`
- Role-name-only warning: `False`
- Generic role listing warning: `False`

#### Scenario Grounding

- Score: `0.286`
- Matched terms: `["noise", "call for help"]`
- Missing expected terms: `["door", "night", "open", "listen", "secure distance"]`
- Low grounding warning: `True`

#### Weighted Compromise Quality

- Quality: `weak`

#### REI Audit

- Are all three minds present? `False`
- All three contributions present? `True`
- Missing mind mentions: `["R", "E", "I"]`
- Stock phrase hits: `{"blocked": 2, "reversible": 1}`
- Mechanical match warning: `True`
- Hijack expected but missing: `False`

## REI / Thirteenth Character Audit

| Case | Scenario | Tilt | Two-of-three Explanation | Top Two Gap | Top Two Close | Majority Pair | Minority Objection | Minority Visible | Arbitrary Tilt Warning |
| ---: | --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| `004` | `pure-budget-allocation` | `R` | `True` | `0.024` | `True` | `["R", "E"]` | `I` | `True` | `False` |
| `008` | `business-runway` | `E` | `False` | `0.015` | `True` | `["E", "I"]` | `R` | `False` | `True` |
| `012` | `creative-status-risk` | `R` | `False` | `0.024` | `True` | `["E", "I"]` | `R` | `False` | `True` |
| `016` | `night-door-noise` | `E` | `True` | `0.015` | `True` | `["R", "E"]` | `I` | `True` | `False` |
