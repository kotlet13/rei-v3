# REI-v3 Codex Plan — Functional Mind Presence Audit and Granite Anchor Workflow

## 0. Purpose

This plan is for Codex.

The current REI-v3 direction is correct:

```text
final synthesis = all three minds present
                + character-weighted compromise
                + situation-activated content
```

The latest audit tooling is a strong improvement, but one important weakness remains:

```text
The audit can pass "all three minds visible" if the final_monologue merely names Racio, Emocio, and Instinkt,
or if it uses shallow keyword markers.
```

This is not enough.

The next upgrade must replace simple name/keyword visibility with **functional mind presence**.

A final synthesis should only pass if each mind contributes its correct REI function:

```text
Racio is functionally present if it contributes calculation, sequence, facts, options, utility, cost, explicit consequence, or rationalization-awareness.

Emocio is functionally present if it contributes image, desire, social meaning, pride/shame, recognition, aliveness, admiration/humiliation, belonging, or expressive value.

Instinkt is functionally present if it contributes threat, loss, boundary, body alarm, trust, attachment, exposure, protection, withdrawal, scarcity, or minimum safety.
```

Merely writing:

```text
"Racio says..., Emocio says..., Instinkt says..."
```

must not pass as good synthesis unless the actual content proves that each processor has a distinct function inside the compromise.

---

## 1. Model strategy

For now, keep using:

```text
granite4.1:30b
```

as the primary quality-anchor model.

Reason:

```text
The goal right now is to stabilize the architecture and evaluation logic while reducing the "model too weak" variable.
```

Do not optimize for small models in this sprint.

Do not remove small-model support.

Do not block future scaling to smaller models.

But for this sprint:

```text
Granite 30B = reference model / quality anchor.
Small models = later regression targets.
```

Add this explicitly to docs and reports:

```text
This run uses Granite 30B as a high-capacity reference model. Passing this run does not prove small-model readiness.
```

The immediate goal is:

```text
Make the evaluation strict enough that even a strong model cannot pass by superficial role naming or canned phrasing.
```

---

## 2. Core correction

Current weak check:

```python
all_three_minds_visible_in_final_monologue = marker words found
```

Required stronger check:

```python
all_three_minds_functionally_present = each mind has a distinct functional contribution
```

A mind is not present just because its name appears.

A mind is present only if it performs its expected role inside the final synthesis.

---

## 3. New audit concepts

Add these fields to `rei_audit`:

```json
{
  "functional_presence": {
    "R": {
      "present": true,
      "score": 0.0,
      "evidence": [],
      "missing_functions": []
    },
    "E": {
      "present": true,
      "score": 0.0,
      "evidence": [],
      "missing_functions": []
    },
    "I": {
      "present": true,
      "score": 0.0,
      "evidence": [],
      "missing_functions": []
    }
  },
  "all_three_minds_functionally_present": true,
  "functional_presence_score": 0.0,
  "role_name_only_warning": false,
  "generic_role_listing_warning": false,
  "weighted_compromise_quality": "good|partial|weak|unknown"
}
```

### Meaning

#### `functional_presence`

Per-mind scoring of whether that mind actually contributes functionally to the synthesis.

#### `all_three_minds_functionally_present`

True only if R, E, and I each pass their functional threshold.

#### `functional_presence_score`

Average of the three mind scores.

#### `role_name_only_warning`

True if the final monologue names a mind but does not show functional evidence for that mind.

#### `generic_role_listing_warning`

True if the final monologue only lists the three processors in generic form without integrating them into the actual decision.

#### `weighted_compromise_quality`

High-level qualitative label based on functional presence, weighted contributions, decision quality, stock phrase density, and profile fit.

---

## 4. Implement functional mind evidence extraction

Modify or extend:

```text
app/backend/rei/weighted_audit.py
```

Add:

```python
def extract_functional_mind_evidence(text: str) -> dict[str, dict[str, object]]:
    ...
```

Return:

```json
{
  "R": {
    "score": 0.75,
    "evidence": ["cost", "sequence", "tradeoff"],
    "missing_functions": []
  },
  "E": {
    "score": 0.5,
    "evidence": ["recognition", "shame"],
    "missing_functions": ["desired image"]
  },
  "I": {
    "score": 0.25,
    "evidence": ["risk"],
    "missing_functions": ["boundary", "loss", "minimum safety"]
  }
}
```

### 4.1 Functional marker groups

Do not use one flat keyword list.

Use grouped functions.

```python
FUNCTIONAL_MARKERS = {
    "R": {
        "facts_or_evidence": [
            "fact", "evidence", "proof", "known", "unknown", "data", "constraint"
        ],
        "calculation_or_tradeoff": [
            "cost", "benefit", "tradeoff", "utility", "material", "probability", "budget", "resource"
        ],
        "sequence_or_plan": [
            "sequence", "order", "timeline", "step", "plan", "execute", "test"
        ],
        "explicit_consequence": [
            "consequence", "if", "then", "result", "outcome", "condition"
        ],
        "rationalization_awareness": [
            "rationalization", "justify", "explanation", "after-the-fact", "reason"
        ]
    },
    "E": {
        "image_or_scene": [
            "image", "scene", "visible", "appearance", "picture", "display", "show"
        ],
        "desire_or_aliveness": [
            "desire", "aliveness", "alive", "pull", "attraction", "longing", "spark"
        ],
        "social_meaning": [
            "recognition", "admiration", "belonging", "status", "audience", "connection", "response"
        ],
        "shame_or_pride": [
            "shame", "pride", "humiliation", "mocked", "embarrassment", "dignity"
        ],
        "expressive_value": [
            "meaning", "beauty", "expression", "creative", "personal", "identity"
        ]
    },
    "I": {
        "threat_or_loss": [
            "threat", "risk", "loss", "danger", "harm", "collapse", "exposure"
        ],
        "body_or_alarm": [
            "body", "alarm", "tension", "freeze", "panic", "breath", "throat", "chest"
        ],
        "boundary_or_trust": [
            "boundary", "trust", "limit", "violation", "distance", "access", "door"
        ],
        "protection_or_withdrawal": [
            "protect", "guard", "withdraw", "hold", "pause", "secure", "shield"
        ],
        "scarcity_or_safety": [
            "safety", "scarcity", "runway", "resource", "minimum", "fallback"
        ]
    }
}
```

### 4.2 Scoring rule

For each mind:

```text
score = number_of_function_groups_hit / total_function_groups
```

Example:

```python
R has 5 function groups.
If final_monologue hits 3 groups:
score = 0.6
```

Threshold:

```python
FUNCTIONAL_PRESENCE_THRESHOLD = 0.4
```

A mind is functionally present if:

```python
score >= 0.4
```

Use 0.4 first because the final monologue may be concise. Later it can be tightened.

### 4.3 Evidence

Store which function groups were hit and which exact markers were found.

Example:

```json
{
  "R": {
    "present": true,
    "score": 0.6,
    "evidence": [
      {"group": "calculation_or_tradeoff", "markers": ["cost", "tradeoff"]},
      {"group": "sequence_or_plan", "markers": ["sequence"]},
      {"group": "explicit_consequence", "markers": ["consequence"]}
    ],
    "missing_functions": ["facts_or_evidence", "rationalization_awareness"]
  }
}
```

---

## 5. Detect name-only presence

Add:

```python
def detect_role_name_only_warning(text: str, functional_presence: dict) -> bool:
    ...
```

Warning if:

```text
The text contains "Racio", "Emocio", or "Instinkt",
but the corresponding functional presence score is below threshold.
```

Example bad output:

```text
"Racio contributes structure, Emocio contributes meaning, Instinkt contributes safety."
```

This may still be too generic.

### 5.1 Generic role listing warning

Add a stronger warning:

```python
def detect_generic_role_listing(text: str) -> bool:
    ...
```

Flag if the monologue mostly contains generic template phrases such as:

```text
Racio contributes...
Emocio contributes...
Instinkt contributes...
weighted compromise...
all three minds...
```

but contains few scenario-specific nouns or allowed options.

Implementation approximation:

```python
GENERIC_SYNTHESIS_PHRASES = [
    "Racio contributes",
    "Emocio contributes",
    "Instinkt contributes",
    "weighted compromise",
    "all three minds",
    "underrepresented signal",
    "character profile",
    "situation-activated"
]
```

If:

```python
generic_phrase_count >= 3
and functional_presence_score < 0.65
```

then:

```python
generic_role_listing_warning = True
```

---

## 6. Add scenario-specific grounding score

A good final monologue must not only mention R/E/I functions. It must also connect them to the actual scenario.

Add:

```json
{
  "scenario_grounding": {
    "score": 0.0,
    "matched_terms": [],
    "missing_expected_terms": []
  }
}
```

### 6.1 Scenario expected grounding terms

Add to each scenario in `scripts/run_granite_weighted_short.py`:

```python
"grounding_terms": [...]
```

Examples:

#### `pure-budget-allocation`

```python
"grounding_terms": [
    "budget", "testing", "design", "infrastructure", "marketing", "allocation", "cost"
]
```

#### `technical-architecture-choice`

```python
"grounding_terms": [
    "architecture", "fast", "brittle", "reliable", "untested", "maintenance", "timeline"
]
```

#### `business-runway`

```python
"grounding_terms": [
    "business", "runway", "paying customer", "stability", "launch", "collapse"
]
```

#### `creative-status-risk`

```python
"grounding_terms": [
    "artist", "exhibition", "bold", "admired", "mocked", "pride", "visible"
]
```

#### `night-door-noise`

```python
"grounding_terms": [
    "door", "noise", "night", "open", "listen", "call for help", "secure distance"
]
```

### 6.2 Scoring

```python
scenario_grounding_score = matched_terms / total_terms
```

Threshold:

```python
SCENARIO_GROUNDING_THRESHOLD = 0.35
```

Flag:

```json
"low_scenario_grounding_warning": true
```

if score is below threshold.

---

## 7. Improve weighted compromise quality label

Add:

```python
def classify_weighted_compromise_quality(audit: dict) -> str:
    ...
```

Rules:

```text
good:
- all three minds functionally present
- all three weighted contributions present
- contribution ranking valid
- tilt matches ranking
- scenario grounding score >= threshold
- no generic_role_listing_warning
- no severe stock phrase warning

partial:
- weighted fields are present
- at least two minds functionally present
- scenario grounding is acceptable
- no severe artifact failure

weak:
- one or more minds missing functionally
- generic role listing warning
- low scenario grounding
- invalid decision extraction
- missing weighted fields

unknown:
- missing final_monologue or missing synthesis fields
```

Add to `rei_audit`:

```json
"weighted_compromise_quality": "good|partial|weak|unknown"
```

Add to summary:

```json
"weighted_compromise_quality_counts": {
  "good": 0,
  "partial": 0,
  "weak": 0,
  "unknown": 0
}
```

---

## 8. Update report.md

In every case detail, add:

```markdown
#### Functional Mind Presence

| Mind | Present | Score | Evidence | Missing Functions |
| --- | --- | ---: | --- | --- |
| R | true | 0.60 | cost, sequence, consequence | rationalization_awareness |
| E | true | 0.40 | image, pride | social_meaning |
| I | true | 0.60 | risk, boundary, safety | body_or_alarm |

- All three functionally present: `true`
- Functional presence score: `0.53`
- Role-name-only warning: `false`
- Generic role listing warning: `false`

#### Scenario Grounding

- Score: `0.57`
- Matched terms: `budget`, `testing`, `infrastructure`
- Missing expected terms: `marketing`
- Low grounding warning: `false`

#### Weighted Compromise Quality

- Quality: `good|partial|weak|unknown`
```

In summary section add:

```markdown
## Functional Presence Summary

- all_three_functionally_present_rate
- average_functional_presence_score
- weighted_compromise_quality_counts
- generic_role_listing_warning_count
- role_name_only_warning_count
- low_scenario_grounding_warning_count
```

---

## 9. Add summary metrics

Add to `summary.json`:

```json
{
  "functional_presence_summary": {
    "all_three_functionally_present": 0,
    "total": 0,
    "rate": 0.0,
    "average_functional_presence_score": 0.0,
    "per_mind_average_score": {
      "R": 0.0,
      "E": 0.0,
      "I": 0.0
    },
    "role_name_only_warning_count": 0,
    "generic_role_listing_warning_count": 0,
    "low_scenario_grounding_warning_count": 0
  },
  "weighted_compromise_quality_counts": {
    "good": 0,
    "partial": 0,
    "weak": 0,
    "unknown": 0
  }
}
```

---

## 10. Update warning codes

Add warning codes:

```text
FUNCTIONAL_MIND_PRESENCE_LOW
ROLE_NAME_ONLY_PRESENCE
GENERIC_ROLE_LISTING
LOW_SCENARIO_GROUNDING
WEIGHTED_COMPROMISE_QUALITY_LOW
```

Warning logic:

```python
if functional_presence_summary["rate"] < 0.8:
    warnings.append("FUNCTIONAL_MIND_PRESENCE_LOW")

if functional_presence_summary["role_name_only_warning_count"] > 0:
    warnings.append("ROLE_NAME_ONLY_PRESENCE")

if functional_presence_summary["generic_role_listing_warning_count"] > 0:
    warnings.append("GENERIC_ROLE_LISTING")

if functional_presence_summary["low_scenario_grounding_warning_count"] > 0:
    warnings.append("LOW_SCENARIO_GROUNDING")

if weighted_compromise_quality_counts["weak"] > 0:
    warnings.append("WEIGHTED_COMPROMISE_QUALITY_LOW")
```

---

## 11. Strengthen strict mode

### 11.1 Add CLI flags

Add:

```bash
--strict-functional
--min-functional-presence-rate 0.80
--min-scenario-grounding-rate 0.80
```

### 11.2 Strict failure conditions

If `--strict-functional` is enabled, fail when:

```text
all_three_functionally_present_rate < min-functional-presence-rate
any role_name_only_warning exists
generic_role_listing_warning_count > 0
low_scenario_grounding_warning_count > allowed threshold
weighted_compromise_quality_counts["weak"] > 0
```

Use defaults:

```text
min-functional-presence-rate = 0.80
min-scenario-grounding-rate = 0.80
```

Do not make this default for all runs yet. Make it opt-in.

Recommended manual audit command:

```bash
python scripts/run_granite_weighted_short.py \
  --manual-audit \
  --confirm-run \
  --strict-artifacts \
  --strict-weighted \
  --strict-functional
```

---

## 12. Improve REI / thirteenth character audit

Current REI warning checks for missing two-of-three explanation, but it may be too keyword-dependent.

Improve it.

For `profile == "REI"`:

Require one of:

```text
- explicit two-of-three / majority language
- or contribution_ranking shows top two close together and final_monologue explains the minority objection
```

Add fields:

```json
{
  "rei_top_two_gap": 0.0,
  "rei_top_two_close": true,
  "rei_minority_objection_visible": true,
  "rei_arbitrary_tilt_warning": false
}
```

Rules:

```python
top_two_gap = top_contribution - second_contribution
rei_top_two_close = top_two_gap <= 0.15
```

If `rei_top_two_close` and final monologue shows all three functionally, do not require literal "two-of-three" phrase.

But if top two are not close and no explanation exists:

```python
rei_arbitrary_tilt_warning = True
```

---

## 13. Update tests

Add tests:

```text
tests/test_functional_presence.py
tests/test_scenario_grounding.py
tests/test_weighted_compromise_quality.py
```

### 13.1 Functional presence tests

Test that this fails:

```text
"Racio contributes structure. Emocio contributes meaning. Instinkt contributes safety."
```

Expected:

```json
generic_role_listing_warning = true
weighted_compromise_quality = "weak" or "partial"
```

Test that this passes:

```text
"Racio keeps the budget allocation tied to cost, sequence, and tradeoff.
 Emocio preserves the visible value of design quality and stakeholder recognition.
 Instinkt keeps the infrastructure risk and delivery boundary from being ignored."
```

Expected:

```json
all_three_minds_functionally_present = true
```

### 13.2 Scenario grounding tests

For `pure-budget-allocation`, a final monologue that contains no budget/testing/design/infrastructure/marketing terms should trigger:

```json
low_scenario_grounding_warning = true
```

### 13.3 Role-name-only tests

If the text contains `Racio`, `Emocio`, `Instinkt` but only Racio has real functional content:

```json
role_name_only_warning = true
missing_mind_mentions_in_final_monologue includes E and I OR functional score for E/I below threshold
```

### 13.4 Quality classification tests

Create fake audits for:

```text
good
partial
weak
unknown
```

Assert correct label.

### 13.5 REI top-two audit tests

For REI:

```text
R=0.36, E=0.34, I=0.30
```

with all three functionally visible should not warn.

But:

```text
R=0.80, E=0.10, I=0.10
```

without explanation should warn.

---

## 14. Keep Granite 30B as quality anchor

Add to docs and runner output:

```text
## Model Interpretation

This run uses Granite 30B as a high-capacity reference model.
The purpose is to test architecture and evaluation strictness before scaling down.
A passing Granite run is not proof that smaller models will pass.
A failing Granite run means the prompt/eval architecture is probably still wrong.
```

Add to `summary.json`:

```json
"model_interpretation": {
  "role": "quality_anchor",
  "small_model_readiness": false,
  "notes": "Granite 30B is used to reduce model weakness as a confounder."
}
```

---

## 15. Do not do yet

Do not:

```text
- switch focus back to small models before functional audit passes on Granite
- expand scenarios
- tune final prompts blindly
- accept role-name-only output as success
- use profile_top_match as primary success metric
- remove legacy fields
```

---

## 16. Success criteria

This upgrade is complete when:

```text
1. Functional mind presence audit exists.
2. Name-only presence no longer passes as full success.
3. Scenario grounding exists.
4. Weighted compromise quality is classified per case.
5. Report includes functional presence table per case.
6. Summary includes functional presence metrics.
7. Strict functional mode can fail weak synthesis.
8. REI thirteenth character audit uses contribution closeness, not only keywords.
9. Tests cover good/partial/weak cases.
10. Manual audit run produces evidence suitable for human review.
```

---

## 17. Recommended run after implementation

First:

```bash
python -m unittest discover tests
```

Then:

```bash
python scripts/run_granite_weighted_short.py \
  --manual-audit \
  --confirm-run \
  --strict-artifacts \
  --strict-weighted \
  --strict-functional
```

Do not run full 65-case test until manual audit passes.

---

## 18. Final instruction for Codex

The project does not need more theory in this step.

It needs stricter evidence.

Make it impossible for the model to pass by merely saying:

```text
Racio, Emocio, and Instinkt are all included.
```

The report must show that they are included functionally.
