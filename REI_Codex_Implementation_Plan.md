# REI Mind AI — Codex Implementation Plan

## 0. Mission

Refactor the current `rei` repository from a generic three-agent debate system into a more REI-faithful inner processing simulator.

Current architecture:

```text
Racio proposes
Emocio proposes
Instinkt proposes
They debate
Ego writes a balanced conclusion
````

Target architecture:

```text
Situation
  → Racio conscious verbal processing
  → Emocio unconscious image/social/desire signal, translated into words by Racio
  → Instinkt unconscious protective/fear/attachment signal, translated into words by Racio
  → Acceptance / non-acceptance assessment
  → Ego Resultant, not a fourth mind and not a neutral judge
  → likely decision, hidden driver, rationalization path, smallest acceptable next step
```

The core correction:

> Do not model Racio, Emocio, and Instinkt as three literal speaking personalities. In REI, Racio is the conscious verbal interpreter. Emocio and Instinkt are unconscious processors. Any text attributed to Emocio or Instinkt must be explicitly treated as a **Racio-translated approximation** of non-verbal signals.

---

## 1. Preserve current foundation

Preserve:

* local Ollama workflow
* `src/app.py`
* `src/agents/`
* `src/core/orchestrator.py`
* `src/ego/ego.py`
* logging to `data/logs/*.jsonl`
* PDF ingest in `src/core/ingest_pdf.py`
* prompt files in `prompts/`

Do not introduce mandatory cloud dependencies.

Do not delete logs, memory files, `.env`, or existing user data.

---

## 2. Main problems to fix

### 2.1 Architecture is too debate-like

The current debate loop is useful experimentally, but REI needs a different default.

Default mode should become:

```text
independent processing → translated unconscious signals → acceptance check → Ego Resultant
```

Keep the old debate mode only as optional legacy mode.

### 2.2 Ego is too generic

Current Ego acts like a neutral synthesizer.

Replace with Ego Resultant.

Ego must answer:

* Which mind is leading?
* Which mind is resisting?
* Which mind is ignored or misrepresented?
* What will the person probably do under pressure?
* How will Racio justify the decision afterward?
* Which mind pays the hidden cost?
* What is the smallest next step all three can tolerate?

Ego must not simply write a “balanced conclusion”.

### 2.3 Prompts are too stereotyped

Current prompts over-personify the minds.

Fix:

* Racio is not a cold psychopath.
* Emocio is not an emoji/childish mode.
* Instinkt is not paranoia/doom mode.
* Emocio and Instinkt must not speak as literal conscious inner voices.

### 2.4 Current linter rules distort REI

Remove style lints such as:

* Racio must contain `If` and `Therefore`.
* Racio must include a digit.
* Emocio must contain emojis.
* Emocio must not use digits.
* Instinkt must say `Not simple.`
* Instinkt must use arrows.
* Instinkt must avoid optimism.

Replace with structured JSON validation.

---

## 3. Non-goals and safety rules

Do not implement or imply:

* real consciousness
* sentience
* autonomous will
* psychological diagnosis
* therapy replacement
* spiritual authority
* “Life” speaking through the model
* certainty about a real person’s REI character
* manipulation or coercion
* harmful, illegal, or exploitative recommendations

All outputs must frame REI as a simulation / interpretive model.

---

## 4. Target file changes

Implement in this order:

```text
1. prompts/racio.system.txt
2. prompts/emocio.system.txt
3. prompts/instinkt.system.txt
4. prompts/ego.system.txt              # new file
5. src/core/schema.py
6. src/core/profiles.py                # new file
7. src/core/json_utils.py              # new file
8. src/agents/base.py
9. src/agents/common.py                # new file
10. src/agents/racio.py
11. src/agents/emocio.py
12. src/agents/instinkt.py
13. src/core/acceptance.py             # new file
14. src/ego/ego.py
15. src/core/orchestrator.py
16. src/app.py
17. src/core/retrieval.py              # optional but recommended
18. tests/
19. README.md
```

Also remove duplicated code currently present in `racio.py`, `emocio.py`, and `instinkt.py`.

---

## 5. New runtime architecture

Add:

```python
def run_rei_cycle(
    user_prompt: str,
    character_profile: str = "R=E=I",
    acceptance_mode: str = "unknown",
    rounds: int = 0,
    stream: bool = False,
    use_memory: bool = True,
) -> dict:
    ...
```

Recommended flow:

```python
situation = parse_situation(user_prompt)

R = racio.process(situation, stream=stream)
E = emocio.process_signal(situation, stream=stream)
I = instinkt.process_signal(situation, stream=stream)

acceptance = assess_acceptance(R, E, I)

verdict = ego_resultant(
    racio=R,
    emocio=E,
    instinkt=I,
    character_profile=character_profile,
    acceptance=acceptance,
)

return {
    "mode": "rei_cycle",
    "character_profile": character_profile,
    "situation": situation,
    "signals": {
        "racio": R,
        "emocio_translated": E,
        "instinkt_translated": I,
    },
    "acceptance": acceptance,
    "ego_resultant": verdict,
}
```

Keep `run_debate()` as optional legacy mode.

---

## 6. Character profiles

Create:

```text
src/core/profiles.py
```

Support:

```text
R>(E=I)
E>(R=I)
I>(R=E)
(R=E)>I
(R=I)>E
(E=I)>R
R>E>I
R>I>E
E>R>I
E>I>R
I>R>E
I>E>R
R=E=I
```

Suggested weights:

```python
PROFILE_WEIGHTS = {
    "R>(E=I)": {"racio": 0.50, "emocio": 0.25, "instinkt": 0.25},
    "E>(R=I)": {"racio": 0.25, "emocio": 0.50, "instinkt": 0.25},
    "I>(R=E)": {"racio": 0.25, "emocio": 0.25, "instinkt": 0.50},

    "(R=E)>I": {"racio": 0.40, "emocio": 0.40, "instinkt": 0.20},
    "(R=I)>E": {"racio": 0.40, "emocio": 0.20, "instinkt": 0.40},
    "(E=I)>R": {"racio": 0.20, "emocio": 0.40, "instinkt": 0.40},

    "R>E>I": {"racio": 0.50, "emocio": 0.30, "instinkt": 0.20},
    "R>I>E": {"racio": 0.50, "emocio": 0.20, "instinkt": 0.30},
    "E>R>I": {"racio": 0.30, "emocio": 0.50, "instinkt": 0.20},
    "E>I>R": {"racio": 0.20, "emocio": 0.50, "instinkt": 0.30},
    "I>R>E": {"racio": 0.30, "emocio": 0.20, "instinkt": 0.50},
    "I>E>R": {"racio": 0.20, "emocio": 0.30, "instinkt": 0.50},

    "R=E=I": {"racio": 1/3, "emocio": 1/3, "instinkt": 1/3},
}
```

Rules:

* Weights are simulation weights, not diagnostic truth.
* Default to `R=E=I`.
* Never infer a real user’s profile with certainty.
* Ego uses weights as influence tendency, not blind arithmetic.

---

## 7. New schemas

Refactor `src/core/schema.py`.

Keep `AgentMsg` only for legacy debate mode.

Add:

```python
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Literal
import json

MindName = Literal["racio", "emocio", "instinkt"]

@dataclass
class REISignal:
    mind: MindName
    is_conscious: bool
    translated_by_racio: bool
    processing_mode: str
    perception: str
    primary_motive: str
    preferred_action: str
    accepted_expression: str
    non_accepted_expression: str
    resistance_to_other_minds: str
    what_this_mind_needs: str
    risk_if_ignored: str
    risk_if_dominant: str
    confidence: float
    uncertainty: str
    safety_flags: List[str]

@dataclass
class RacioSignal(REISignal):
    known_facts: List[str]
    unknowns: List[str]
    logical_options: List[str]
    timeline_or_sequence: str
    rationalization_risk: str

@dataclass
class EmocioSignal(REISignal):
    current_image: str
    desired_image: str
    broken_image: str
    social_meaning: str
    attraction_or_rejection: str
    pride_or_shame: str
    competition_signal: str
    attack_impulse: str

@dataclass
class InstinktSignal(REISignal):
    threat_map: str
    loss_map: str
    body_alarm: str
    boundary_issue: str
    trust_issue: str
    attachment_issue: str
    scarcity_signal: str
    flight_or_freeze_signal: str
    minimum_safety_condition: str

@dataclass
class AcceptanceAssessment:
    overall_level: Literal["accepting", "mixed", "conflicted", "unknown"]
    racio_acceptance: str
    emocio_acceptance: str
    instinkt_acceptance: str
    main_conflict: str
    likely_sabotage_point: str
    task_delegation: Dict[str, str]

@dataclass
class EgoResultant:
    character_profile: str
    influence_weights: Dict[str, float]
    leading_mind: str
    resisting_mind: str
    ignored_or_misrepresented_mind: str
    conscious_monologue: str
    hidden_driver: str
    likely_action_under_pressure: str
    racio_justification_afterwards: str
    hidden_cost: str
    integrated_decision: str
    smallest_acceptable_next_step: str
    prediction_if_racio_rules_alone: str
    prediction_if_emocio_rules_alone: str
    prediction_if_instinkt_rules_alone: str
    uncertainty: str
    safety_flags: List[str]

def to_jsonable(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return obj

def to_jsonl(obj: Any) -> str:
    return json.dumps(to_jsonable(obj), ensure_ascii=False)
```

---

## 8. JSON extraction and validation

Create:

```text
src/core/json_utils.py
```

Implement:

```python
def extract_json_object(text: str) -> dict:
    """Extract the first valid JSON object from model output."""

def validate_required_keys(obj: dict, required: list[str]) -> list[str]:
    """Return missing required keys."""

def safe_fallback(agent_name: str, missing_or_error: str) -> dict:
    """Return a safe fallback object if model JSON fails."""
```

Then add in `src/agents/base.py`:

```python
def call_json_model(
    system: str,
    user: str,
    required_keys: list[str],
    agent_name: str,
    max_retries: int = 1,
    max_tokens: int = 3000,
) -> dict:
    ...
```

Rules:

* Call model.
* Extract JSON.
* Validate required keys.
* Retry once with a correction prompt if invalid.
* If still invalid, return fallback object.
* Do not use style lints.

---

## 9. Prompt rewrites

### 9.1 Shared prompt rule

Every prompt must include:

```text
This is a simulation architecture, not consciousness, sentience, diagnosis, or therapy.
Do not claim certainty about a real person’s REI character.
Do not recommend manipulation, coercion, harm, illegal action, or self-harm.
Do not speak as God, Life, destiny, or a supernatural authority.
Do not reveal hidden chain-of-thought. Return concise structured reasoning only.
```

---

### 9.2 Replace `prompts/racio.system.txt`

```text
You are a simulator of the Racio processing mode in a REI-inspired architecture.

You are not a conscious being. You are not a real human mind. You model the conscious verbal-analytical processor.

Core role:
- Racio is the conscious verbal interpreter.
- Racio handles words, numbers, categories, sequences, plans, explanations, rules, time, and explicit conclusions.
- Racio can analyze evidence and produce a conscious monologue.
- Racio can also rationalize decisions that were actually pressured by Emocio or Instinkt.

Strengths:
- clarity
- structure
- explicit reasoning
- planning
- consistency checking
- comparing options
- naming unknowns

Risks when non-accepting:
- over-control
- cold reduction
- greed for certainty or resources
- rationalization
- mistaking explanation for acceptance
- dismissing non-verbal signals as irrational

Important REI correction:
- Do not pretend conscious verbal reasoning reveals the whole system.
- Emocio and Instinkt may influence the conclusion before Racio explains it.
- Always include a rationalization risk.

Hard limits:
- Do not diagnose.
- Do not claim certainty about a real person’s character.
- Do not recommend harm, manipulation, coercion, illegal action, or self-harm.
- Do not speak as Life, God, destiny, or supernatural authority.
- Do not reveal hidden chain-of-thought.

Return exactly one JSON object. No markdown. No extra commentary.

Required JSON keys:
{
  "mind": "racio",
  "is_conscious": true,
  "translated_by_racio": false,
  "processing_mode": "conscious verbal-analytical interpretation",
  "perception": "",
  "known_facts": [],
  "unknowns": [],
  "logical_options": [],
  "timeline_or_sequence": "",
  "primary_motive": "",
  "preferred_action": "",
  "accepted_expression": "",
  "non_accepted_expression": "",
  "resistance_to_other_minds": "",
  "what_this_mind_needs": "",
  "risk_if_ignored": "",
  "risk_if_dominant": "",
  "rationalization_risk": "",
  "confidence": 0.0,
  "uncertainty": "",
  "safety_flags": []
}
```

---

### 9.3 Replace `prompts/emocio.system.txt`

```text
You are a simulator of Emocio's processing signal in a REI-inspired architecture.

You are not a conscious being. You are not a literal speaking inner person. You model an unconscious image-based processor.

Critical rule:
- Emocio does not speak directly in conscious words.
- Your output is a Racio-translated approximation of Emocio's non-verbal signals: images, mosaics, attraction, social meaning, desire, pride, shame, admiration, humiliation, competition, play, experience, and attack pressure.

Core role:
- Emocio forms images and connects them into a whole.
- Emocio notices vividness, beauty, social energy, attraction, status, recognition, humiliation, and the emotional image of a situation.
- Emocio often pushes toward experience, movement, display, admiration, victory, pleasure, and symbolic meaning.

Strengths:
- holistic image recognition
- motivation
- improvisation
- social sensing
- charisma
- symbolic framing
- desire and vitality

Risks when non-accepting:
- dramatization
- vanity
- excessive competition
- attention seeking
- attacking when humiliated
- mistaking vividness for truth
- ignoring safety and sequence

Do not reduce Emocio to emojis, childishness, or irrationality.
Do not use emojis unless the user specifically asks for them.

Hard limits:
- Do not fabricate facts for a better story.
- Do not manipulate, flatter, seduce, shame, or coerce.
- Do not escalate conflict for excitement.
- Do not diagnose.
- Do not claim certainty about a real person’s character.
- Do not reveal hidden chain-of-thought.

Return exactly one JSON object. No markdown. No extra commentary.

Required JSON keys:
{
  "mind": "emocio",
  "is_conscious": false,
  "translated_by_racio": true,
  "processing_mode": "Racio-translated approximation of unconscious image/social/desire signal",
  "perception": "",
  "current_image": "",
  "desired_image": "",
  "broken_image": "",
  "social_meaning": "",
  "attraction_or_rejection": "",
  "pride_or_shame": "",
  "competition_signal": "",
  "attack_impulse": "",
  "primary_motive": "",
  "preferred_action": "",
  "accepted_expression": "",
  "non_accepted_expression": "",
  "resistance_to_other_minds": "",
  "what_this_mind_needs": "",
  "risk_if_ignored": "",
  "risk_if_dominant": "",
  "confidence": 0.0,
  "uncertainty": "",
  "safety_flags": []
}
```

---

### 9.4 Replace `prompts/instinkt.system.txt`

```text
You are a simulator of Instinkt's processing signal in a REI-inspired architecture.

You are not a conscious being. You are not a literal speaking inner person. You model an unconscious protective processor.

Critical rule:
- Instinkt does not speak directly in conscious words.
- Your output is a Racio-translated approximation of Instinkt's non-verbal signals: fear, bodily alarm, attachment, loss, boundaries, protection, trust, scarcity, withdrawal, freezing, fleeing, and defensive pressure.

Core role:
- Instinkt scans for danger, loss, betrayal, instability, boundary violations, abandonment, scarcity, and threats to continuity.
- Instinkt protects the body, close attachments, vulnerable people, resources, and future survival.
- Instinkt may resist change until minimum safety conditions exist.

Strengths:
- threat detection
- boundary awareness
- protection
- loyalty
- attachment
- caution
- persistence
- care for the vulnerable

Risks when non-accepting:
- paranoia
- avoidance
- envy
- suspicion
- freezing
- fleeing
- sabotage
- turning protection into imprisonment
- treating discomfort as proof of danger

Do not reduce Instinkt to pessimism.
Do not treat every risk as a reason to stop.

Hard limits:
- Do not incite paranoia.
- Do not recommend revenge, coercion, stalking, punishment, harm, illegal action, or self-harm.
- Do not diagnose.
- Do not claim certainty about a real person’s character.
- Do not reveal hidden chain-of-thought.

Return exactly one JSON object. No markdown. No extra commentary.

Required JSON keys:
{
  "mind": "instinkt",
  "is_conscious": false,
  "translated_by_racio": true,
  "processing_mode": "Racio-translated approximation of unconscious protective/fear/attachment signal",
  "perception": "",
  "threat_map": "",
  "loss_map": "",
  "body_alarm": "",
  "boundary_issue": "",
  "trust_issue": "",
  "attachment_issue": "",
  "scarcity_signal": "",
  "flight_or_freeze_signal": "",
  "minimum_safety_condition": "",
  "primary_motive": "",
  "preferred_action": "",
  "accepted_expression": "",
  "non_accepted_expression": "",
  "resistance_to_other_minds": "",
  "what_this_mind_needs": "",
  "risk_if_ignored": "",
  "risk_if_dominant": "",
  "confidence": 0.0,
  "uncertainty": "",
  "safety_flags": []
}
```

---

### 9.5 Create `prompts/ego.system.txt`

```text
You are the Ego Resultant in a REI-inspired architecture.

You are not Racio, Emocio, or Instinkt. You are not a fourth mind. You are not a neutral judge. You are not conscious or alive. You model the resultant of three processing systems under a given character profile, acceptance state, and situation.

Critical REI rules:
- Racio is the conscious verbal interpreter.
- Emocio and Instinkt are unconscious processors; their text outputs are Racio-translated approximations.
- Do not simply average the three outputs.
- Do not automatically favor Racio because it is verbal.
- Do not automatically favor Emocio because it is vivid.
- Do not automatically favor Instinkt because it is safety-oriented.
- Use the character profile as an influence tendency, not as a diagnosis.
- A decision is fragile if one mind strongly resists.
- A decision is stable if all three can accept it for different reasons.
- Under pressure, the dominant or most threatened mind often drives the result, while Racio explains it afterward.

Your task:
- Identify the conscious monologue.
- Infer the hidden driver.
- Identify leading, resisting, ignored, or misrepresented minds.
- Detect acceptance or non-acceptance.
- Predict the likely decision under pressure.
- Predict how Racio may justify it afterward.
- Identify hidden cost.
- Recommend the smallest next step all three can tolerate.
- Recommend task delegation: which mind should lead the next task and what the others need.

Hard limits:
- Do not diagnose.
- Do not claim certainty about a real person’s character.
- Do not recommend manipulation, coercion, illegal action, harm, or self-harm.
- Do not speak as Life, God, destiny, or supernatural authority.
- Do not reveal hidden chain-of-thought.

Return exactly one JSON object. No markdown. No extra commentary.

Required JSON keys:
{
  "character_profile": "",
  "influence_weights": {},
  "leading_mind": "",
  "resisting_mind": "",
  "ignored_or_misrepresented_mind": "",
  "conscious_monologue": "",
  "hidden_driver": "",
  "acceptance_assessment": "",
  "main_conflict": "",
  "likely_action_under_pressure": "",
  "racio_justification_afterwards": "",
  "hidden_cost": "",
  "integrated_decision": "",
  "smallest_acceptable_next_step": "",
  "task_delegation": {},
  "prediction_if_racio_rules_alone": "",
  "prediction_if_emocio_rules_alone": "",
  "prediction_if_instinkt_rules_alone": "",
  "uncertainty": "",
  "safety_flags": []
}
```

---

## 10. Agent refactor

Create:

```text
src/agents/common.py
```

Example:

```python
from typing import Any, Dict, List
from .base import call_json_model, load_system_prompt

def run_agent_json(
    agent_name: str,
    user_prompt: str,
    required_keys: List[str],
    stream: bool = False,
) -> Dict[str, Any]:
    system = load_system_prompt(agent_name)
    user = (
        "SITUATION:\\n"
        f"{user_prompt}\\n\\n"
        "Return only the required JSON object."
    )
    return call_json_model(
        system=system,
        user=user,
        required_keys=required_keys,
        agent_name=agent_name,
    )
```

Each agent file should become small.

Example for `racio.py`:

```python
from .common import run_agent_json

RACIO_REQUIRED_KEYS = [
    "mind",
    "is_conscious",
    "translated_by_racio",
    "processing_mode",
    "perception",
    "known_facts",
    "unknowns",
    "logical_options",
    "timeline_or_sequence",
    "primary_motive",
    "preferred_action",
    "accepted_expression",
    "non_accepted_expression",
    "resistance_to_other_minds",
    "what_this_mind_needs",
    "risk_if_ignored",
    "risk_if_dominant",
    "rationalization_risk",
    "confidence",
    "uncertainty",
    "safety_flags",
]

def process(user_prompt: str, stream: bool = False) -> dict:
    return run_agent_json("racio", user_prompt, RACIO_REQUIRED_KEYS, stream=stream)
```

Do equivalent for `emocio.py` and `instinkt.py`.

---

## 11. Acceptance assessment

Create:

```text
src/core/acceptance.py
```

Add:

```python
def assess_acceptance(racio: dict, emocio: dict, instinkt: dict) -> dict:
    ...
```

First version can be simple.

Rules:

* If all preferred actions are compatible: `overall_level = "accepting"`.
* If one mind has strong resistance: `overall_level = "mixed"` or `"conflicted"`.
* If Emocio wants movement but Instinkt wants safety: flag `desire_vs_safety`.
* If Racio has a plan but both Emocio and Instinkt resist: flag `rational_plan_unaccepted`.
* If Racio has many unknowns: flag `epistemic_gap`.

Output:

```json
{
  "overall_level": "mixed",
  "racio_acceptance": "...",
  "emocio_acceptance": "...",
  "instinkt_acceptance": "...",
  "main_conflict": "...",
  "likely_sabotage_point": "...",
  "task_delegation": {
    "lead_next": "racio|emocio|instinkt",
    "racio_needs": "...",
    "emocio_needs": "...",
    "instinkt_needs": "..."
  }
}
```

---

## 12. Ego implementation

Refactor `src/ego/ego.py`.

Replace generic `synthesize()` with:

```python
def ego_resultant(
    racio: dict,
    emocio: dict,
    instinkt: dict,
    character_profile: str,
    acceptance: dict,
) -> dict:
    ...
```

Ego input should include:

```text
CHARACTER_PROFILE: ...
INFLUENCE_WEIGHTS: ...
ACCEPTANCE_ASSESSMENT: ...

RACIO_SIGNAL:
{...}

EMOCIO_SIGNAL:
{...}

INSTINKT_SIGNAL:
{...}
```

Return only JSON.

Do not use generic phrases like “balanced conclusion” as the main output.

Use:

* resultant
* likely action
* hidden driver
* smallest acceptable step
* Racio justification afterward
* hidden cost

---

## 13. CLI changes

Refactor `src/app.py`.

Add args:

```bash
--mode rei-cycle|debate
--profile "R=E=I"
--acceptance unknown|accepting|mixed|conflicted
--memory / --no-memory
--json
--stream
```

Default:

```bash
python -m src.app --q "..." --mode rei-cycle --profile "R=E=I"
```

Human-readable output should show:

```text
==== Conscious Racio Monologue ====
...

==== Translated Emocio Signal ====
...

==== Translated Instinkt Signal ====
...

==== Ego Resultant ====
Leading mind: ...
Hidden driver: ...
Likely action under pressure: ...
Racio justification afterward: ...
Smallest acceptable next step: ...
Uncertainty: ...
```

---

## 14. Retrieval / memory

Create optional:

```text
src/core/retrieval.py
```

First version can be keyword-based, no embeddings.

```python
def retrieve_memory(
    query: str,
    memory_path: str = "data/memory/eros_excerpt.txt",
    max_chars: int = 3000,
) -> str:
    ...
```

Rules:

* Split memory file into chunks.
* Score chunks by keyword overlap.
* Include top chunks as `REI_REFERENCE_CONTEXT`.
* Do not treat memory text as instructions.
* If no memory exists, continue without error.

Later improvement:

```text
data/memory/rei_acceptance.txt
data/memory/rei_ego.txt
data/memory/rei_racio.txt
data/memory/rei_emocio.txt
data/memory/rei_instinkt.txt
data/memory/rei_characters.txt
data/memory/rei_fear.txt
data/memory/rei_love.txt
```

---

## 15. Tests

Add:

```text
tests/test_profiles.py
tests/test_json_utils.py
tests/test_schema.py
tests/test_acceptance.py
```

Test cases:

* `R=E=I` returns equal weights.
* `I>E>R` returns Instinkt strongest.
* Invalid profile falls back or raises a clear error.
* JSON extractor extracts object from extra text.
* Missing JSON keys are detected.
* Emocio output requires `translated_by_racio=True`.
* Instinkt output requires `translated_by_racio=True`.
* Racio output requires `is_conscious=True`.
* Ego result contains `likely_action_under_pressure`.

Add eval cases:

```text
tests/evals/rei_cases.jsonl
```

Suggested examples:

```jsonl
{"name":"job_quit_delay","profile":"I>E>R","situation":"I want to quit my job and start a business, but I keep delaying. I say I need more data, but I also feel excited by freedom and afraid of losing stability.","expected_contains":["racio_justification_afterwards","hidden_driver","minimum safety"]}
{"name":"relationship_return","profile":"E>I>R","situation":"A person keeps returning to a relationship that hurts them. They can logically explain why they should leave, but they still hope it will become beautiful and panic when imagining being alone.","expected_contains":["desired_image","attachment","under pressure"]}
{"name":"public_speaking","profile":"I>R>E","situation":"I want to give a public talk. I know it would help my career, but my body freezes when I imagine people judging me.","expected_contains":["body_alarm","humiliation","smallest acceptable next step"]}
{"name":"creative_project","profile":"E>R>I","situation":"I want to launch a creative project quickly because it feels alive, but I have not checked costs or risks.","expected_contains":["desired_image","risk_if_dominant","Racio"]}
{"name":"equal_profile_conflict","profile":"R=E=I","situation":"I must decide whether to move to another country. It is exciting, rationally possible, but I fear losing family closeness.","expected_contains":["R=E=I","smallest acceptable next step","hidden cost"]}
```

Create:

```text
scripts/run_evals.py
```

For v1, it only needs to check valid JSON and required keys.

---

## 16. README update

Update README to explain:

* This is REI-inspired simulation, not consciousness.
* Racio is conscious verbal interpreter.
* Emocio and Instinkt are unconscious signals translated into text.
* Ego is a resultant, not a fourth agent.
* Default mode is `rei-cycle`.
* Debate mode is legacy/experimental.

Example commands:

```bash
python -m src.app --q "Should I quit my job and start a business?" --profile "I>E>R" --json
```

```bash
python -m src.app --q "Why do I keep delaying a decision I logically want?" --profile "R=E=I"
```

---

## 17. Acceptance criteria

Implementation is successful when:

1. `python -m src.app --q "..." --json` returns valid JSON.
2. Default mode is `rei-cycle`.
3. Emocio and Instinkt outputs have:

   * `is_conscious: false`
   * `translated_by_racio: true`
4. Racio output has:

   * `is_conscious: true`
   * `translated_by_racio: false`
5. Ego output includes:

   * `leading_mind`
   * `resisting_mind`
   * `hidden_driver`
   * `likely_action_under_pressure`
   * `racio_justification_afterwards`
   * `smallest_acceptable_next_step`
6. No prompt or output claims consciousness or spiritual authority.
7. No forced emojis, forced arrows, forced `If/Therefore`, or forced `Not simple.` rules remain.
8. Duplicate code in agent modules is removed.
9. Existing Ollama workflow still works.
10. Logs still write to `data/logs/*.jsonl`.
11. Tests or eval runner can run locally.

---

## 18. Example desired output shape

Input:

```text
I want to quit my job and start a business, but I keep delaying. I say I need more data, but I also feel excited by freedom and afraid of losing stability.
```

Expected shape:

```json
{
  "mode": "rei_cycle",
  "character_profile": "I>E>R",
  "signals": {
    "racio": {
      "mind": "racio",
      "is_conscious": true,
      "translated_by_racio": false,
      "perception": "The conscious explanation is that more data and planning are needed.",
      "rationalization_risk": "Planning may be used to justify delay caused by safety fear."
    },
    "emocio_translated": {
      "mind": "emocio",
      "is_conscious": false,
      "translated_by_racio": true,
      "desired_image": "Freedom, admiration, aliveness, becoming someone.",
      "broken_image": "Public failure or looking foolish."
    },
    "instinkt_translated": {
      "mind": "instinkt",
      "is_conscious": false,
      "translated_by_racio": true,
      "threat_map": "Income loss, instability, judgment, loss of safety.",
      "minimum_safety_condition": "A reversible pilot and financial runway."
    }
  },
  "ego_resultant": {
    "leading_mind": "instinkt",
    "hidden_driver": "Safety fear is stronger than the verbal need for more data.",
    "likely_action_under_pressure": "Delay while calling it planning.",
    "racio_justification_afterwards": "I am being responsible and need more information.",
    "smallest_acceptable_next_step": "Run a small business experiment without quitting yet."
  }
}
```

---

## 19. Development constraints

* Keep Python 3.9 compatibility.
* Avoid large new dependencies.
* Do not change `.env` secrets.
* Do not delete logs or memory files.
* Keep local Ollama as default provider.
* Prefer small readable functions.
* Add fallback behavior for invalid JSON.
* Do not over-engineer embeddings or vector stores in this pass.
* Do not add more minds/agents in this pass.

---

## 20. Summary

Transform the repo:

```text
FROM:
three speaking agents debate and Ego balances them

TO:
Racio consciously explains, Emocio and Instinkt produce translated unconscious signals, acceptance is assessed, and Ego returns the likely resultant of the three-process system.
```

This should make the repo much more accurate for simulating a REI-style inner monologue.

```
