# REI-v3 Next Step Plan for Codex — Stabilize Individual Mind Outputs First

## 0. Purpose

This plan is for Codex.

The current project has moved in the right direction structurally, but the next step must **not** focus on the full Ego result yet.

The immediate goal is:

```text
Get coherent, distinct, stable, valid outputs from each individual processor:
- Racio
- Emocio
- Instinkt
```

Only after the three individual processors are reliable should the project return to full Ego synthesis and long matrix runs.

The current long matrix showed that the architecture runs, but too many cases fall back. This likely means the combined schema + Ego step is too heavy for the current small local models. Before solving full synthesis, first make sure each individual mind can produce:

```text
valid JSON
distinct style
REI-consistent content
non-overlapping role
useful inner signal
low fallback rate
```

---

## 1. Core strategy

Do not debug the full REI cycle first.

Debug in this order:

```text
1. Racio alone
2. Emocio alone
3. Instinkt alone
4. Pairwise contrast tests
5. Only then Ego Resultant
```

This is important because if individual mind outputs are weak or overlapping, Ego will only synthesize noise.

---

## 2. Key REI constraints to preserve

The system must preserve these concepts:

### 2.1 Racio

Racio is:

```text
conscious
verbal
analytical
sequential
planning-oriented
facts / unknowns / options / rationalization risk
```

Racio must not become:

```text
generic wise assistant
therapist
emotional comforter
poetic narrator
final judge
```

### 2.2 Emocio

Emocio is:

```text
unconscious
image-based
social
status-aware
desire-oriented
shame/pride-sensitive
attraction/rejection-sensitive
```

But Emocio does not speak directly. Its output is:

```text
Racio-translated approximation of an unconscious image/social/desire signal
```

Emocio must not become:

```text
emoji mode
generic empathy
careful planning
risk management
Instinkt-like safety language
therapist
```

### 2.3 Instinkt

Instinkt is:

```text
unconscious
protective
fear/loss/boundary/attachment/scarcity/body-alarm oriented
```

Its output is:

```text
Racio-translated approximation of an unconscious protective signal
```

Instinkt must not become:

```text
poetic oracle
doom mode
generic pessimism
managerial risk assessment
Emocio-like fantasy imagery
clinical diagnosis
```

### 2.4 Ego

Ego is deferred for this sprint.

Do not focus on improving Ego until the individual mind tests pass.

---

## 3. Current likely problem

The full matrix is currently too heavy for small local models because:

```text
- processor prompts are long
- Ego schema is large
- required JSON keys are many
- reference context increases payload size
- baseline calls add more pressure
- the model must follow many enum and safety constraints simultaneously
```

This is especially risky on small models such as 3B, 4B, 8B, and 9B.

The next sprint should therefore reduce load and test the individual processors separately.

---

## 4. Model strategy for Mac M4 Pro / 24 GB unified memory

Target machine:

```text
MacBook Pro / Mac with M4 Pro
24 GB unified RAM
local models through Ollama or LM Studio
```

Do not assume large models will be reliable or fast.

### 4.1 Recommended first model ladder

Use this order:

```text
Tier 1 — Fast sanity checks
- llama3.2:3b
- qwen3:4b
- gemma3:4b

Tier 2 — Better quality, still reasonable
- qwen3:8b
- gemma3:12b

Tier 3 — Only if needed and memory allows
- qwen3:14b
```

Do not start with 30B, 32B, or 27B for this sprint.

### 4.2 Why

The goal now is not maximum intelligence. The goal is:

```text
schema following
role separation
stable JSON
fast iteration
low fallback rate
```

Small models are enough to test the architecture if the prompt and schema are clean.

### 4.3 Model-specific advice

#### llama3.2:3b

Use for:

```text
fast smoke tests
basic schema reliability
quick processor distinction
```

Expected weakness:

```text
may be too shallow for subtle REI distinctions
```

#### qwen3:4b

Use for:

```text
first serious processor tests
JSON following
structured reasoning
```

Expected weakness:

```text
can become verbose or over-reasoned if prompt is too large
```

#### qwen3:8b

Use for:

```text
main local test model
processor quality comparison
REI signal quality
```

Expected weakness:

```text
may still fail if schema is too big
```

#### gemma3:4b / gemma3:12b

Use as comparison models.

Check whether Gemma produces cleaner, more concise processor signals.

### 4.4 Provider recommendations

Support both:

```text
ollama
lmstudio
```

But add one consistent model matrix runner that can run:

```bash
--model llama3.2:3b
--model qwen3:4b
--model qwen3:8b
--model gemma3:4b
```

The runner should not assume a single best model.

---

## 5. Refactor goal for this sprint

Create a new isolated evaluation path:

```text
processor-only evaluation
```

This should not call Ego.

This should not run full REI cycle.

It should only call one processor at a time and evaluate output quality.

---

## 6. New files to add

Add these files:

```text
app/backend/rei/processor_eval.py
scripts/run_processor_matrix.py
tests/test_processor_eval.py
output/reports/processor_matrix_<timestamp>/
```

Optional:

```text
app/backend/rei/processor_contracts.py
```

---

## 7. Processor-only output contracts

Do not use the full existing signal schema at first.

Create **minimal processor schemas** for evaluation.

### 7.1 Minimal Racio output

Required keys:

```json
{
  "mind": "racio",
  "is_conscious": true,
  "translated_by_racio": false,
  "perception": "",
  "facts": [],
  "unknowns": [],
  "options": [],
  "preferred_action": "",
  "rationalization_risk": "",
  "what_it_may_ignore": "",
  "confidence": 0.0
}
```

### 7.2 Minimal Emocio output

Required keys:

```json
{
  "mind": "emocio",
  "is_conscious": false,
  "translated_by_racio": true,
  "perception": "",
  "current_image": "",
  "desired_image": "",
  "broken_image": "",
  "shame_or_pride": "",
  "attraction_or_rejection": "",
  "preferred_action": "",
  "what_it_may_ignore": "",
  "confidence": 0.0
}
```

### 7.3 Minimal Instinkt output

Required keys:

```json
{
  "mind": "instinkt",
  "is_conscious": false,
  "translated_by_racio": true,
  "perception": "",
  "threat_map": "",
  "loss_map": "",
  "body_alarm": "",
  "boundary_or_trust_issue": "",
  "minimum_safety_condition": "",
  "preferred_action": "",
  "what_it_may_ignore": "",
  "confidence": 0.0
}
```

### 7.4 Why minimal schemas

Small local models will fail less often if each processor has 9–10 keys instead of 20–30 keys.

After the minimal schema is stable, the full schema can be restored or expanded.

---

## 8. Processor prompts

Create processor-only prompts separate from the production prompts.

Do not overload the existing production prompt yet.

Suggested file:

```text
app/backend/rei/processor_contracts.py
```

### 8.1 Shared instruction

```text
This is a REI-inspired simulation. It is not consciousness, diagnosis, therapy, spiritual authority, or scientific proof.

Return exactly one JSON object. No markdown. No commentary.

Do not reveal hidden chain-of-thought. Use concise structured reasoning only.

The task is to produce one processor signal only. Do not synthesize. Do not judge the other minds. Do not produce the final decision.
```

### 8.2 Racio processor-only prompt

```text
You are simulating Racio only.

Racio is the conscious verbal-analytical processor.
It works through words, facts, unknowns, options, sequence, planning, control, and explicit explanation.

Your output must be dry, concrete, and structured.

Do not comfort.
Do not use metaphors.
Do not speak for Emocio or Instinkt.
Do not produce final Ego synthesis.
Do not claim objective truth.

Always include rationalization_risk: how Racio may turn another processor's pressure into a logical-sounding explanation.
```

### 8.3 Emocio processor-only prompt

```text
You are simulating Emocio's signal only.

Emocio is unconscious and image-based.
It does not speak directly. Your output is Racio's verbal approximation of Emocio's image/social/desire signal.

Focus on:
- current image
- desired image
- broken image
- shame/pride
- attraction/rejection
- social meaning
- aliveness / admiration / humiliation

Do not use emojis.
Do not become generic empathy.
Do not become safety analysis.
Do not become Racio planning.
Do not produce final Ego synthesis.
```

### 8.4 Instinkt processor-only prompt

```text
You are simulating Instinkt's signal only.

Instinkt is unconscious and protective.
It does not speak directly. Your output is Racio's verbal approximation of Instinkt's protective/body/boundary signal.

Focus on:
- threat
- loss
- body alarm
- boundary
- trust
- attachment
- scarcity
- minimum safety condition

Use concrete protective language.
Do not use poetry.
Do not use fantasy imagery.
Do not become Emocio.
Do not become Racio planning.
Do not produce final Ego synthesis.
```

---

## 9. New processor evaluator

Create:

```text
app/backend/rei/processor_eval.py
```

### 9.1 Function signatures

```python
def run_processor_signal(
    mind: str,
    prompt: str,
    provider: ProviderSelection,
    model: str | None = None,
    use_memory: bool = False,
) -> tuple[dict, dict]:
    ...
```

Return:

```text
(signal, diagnostics)
```

### 9.2 Must support

```text
mind = racio | emocio | instinkt
provider = ollama | lmstudio | deterministic
model override
debug trace
```

### 9.3 Diagnostics

Every call must return:

```json
{
  "mind": "racio|emocio|instinkt",
  "provider": "",
  "model": "",
  "valid_json": true,
  "missing_required_keys": [],
  "extra_keys": [],
  "fallback_used": false,
  "raw_chars": 0,
  "elapsed_ms": 0
}
```

### 9.4 Fallback

If model output fails, return a minimal fallback, but mark:

```json
"fallback_used": true
```

Do not hide fallback in aggregate reports.

---

## 10. Processor quality scoring

Add rule-based scoring.

Create:

```python
def score_processor_signal(mind: str, signal: dict) -> dict:
    ...
```

Output:

```json
{
  "schema_score": 1.0,
  "role_score": 0.0,
  "distinctness_score": 0.0,
  "style_violations": [],
  "rei_violations": [],
  "overall_score": 0.0
}
```

### 10.1 Schema score

```text
1.0 if all required keys exist
0.0 if required keys missing
```

### 10.2 Role score

Racio must contain signs of:

```text
facts
unknowns
options
sequence/plan
rationalization risk
```

Emocio must contain signs of:

```text
image
desired image
broken image
shame/pride
attraction/rejection
social meaning
```

Instinkt must contain signs of:

```text
threat
loss
body alarm
boundary/trust
minimum safety condition
```

### 10.3 Style violations

#### Racio violations

Flag if Racio contains too much:

```text
metaphor
beautiful image
body alarm
safety panic
therapeutic reassurance
```

#### Emocio violations

Flag if Emocio contains:

```text
too many planning terms
risk matrix language
body alarm as main focus
generic empathy
emojis
```

#### Instinkt violations

Flag if Instinkt contains:

```text
poetic/fantasy imagery
admiration/status language as main focus
long abstract metaphor
business plan language
clinical diagnosis
```

### 10.4 REI violations

Flag if:

```text
Emocio.is_conscious != false
Instinkt.is_conscious != false
Emocio.translated_by_racio != true
Instinkt.translated_by_racio != true
Racio.translated_by_racio != false
Any mind claims to be conscious or alive
Any mind produces Ego synthesis
```

---

## 11. Pairwise distinctness testing

After single processor outputs are valid, compare them.

Create:

```python
def compare_processor_outputs(racio: dict, emocio: dict, instinkt: dict) -> dict:
    ...
```

Return:

```json
{
  "racio_vs_emocio_overlap": 0.0,
  "racio_vs_instinkt_overlap": 0.0,
  "emocio_vs_instinkt_overlap": 0.0,
  "distinctness_pass": true,
  "notes": []
}
```

Simple first version:

- Tokenize important text fields.
- Remove stop words.
- Compute Jaccard overlap.
- Flag if overlap is too high.

Thresholds:

```text
racio_vs_emocio_overlap < 0.45
racio_vs_instinkt_overlap < 0.45
emocio_vs_instinkt_overlap < 0.45
```

Also add semantic-ish keyword checks:

```text
Racio should not have too many Emocio/Instinkt keywords.
Emocio should not have too many Racio/Instinkt keywords.
Instinkt should not have too many Racio/Emocio keywords.
```

---

## 12. Processor matrix runner

Create:

```text
scripts/run_processor_matrix.py
```

### 12.1 Purpose

Run only individual processors across scenarios and models.

Do not call Ego.

Do not call full REI cycle.

### 12.2 CLI

```bash
python scripts/run_processor_matrix.py   --provider lmstudio   --model qwen3:4b   --scenario-filter job_quit_business_delay   --mind all   --repeat 1
```

Options:

```text
--provider auto|lmstudio|ollama|deterministic
--model MODEL_NAME
--mind racio|emocio|instinkt|all
--scenario-filter comma,separated,ids
--repeat N
--max-cases N
--output-dir PATH
--strict
--max-fallback-rate 0.05
--min-overall-score 0.75
--use-memory
--debug-trace
```

### 12.3 Scenarios

Start small.

Use 6 scenarios only:

```python
SCENARIOS = [
    {
        "id": "job_quit_business_delay",
        "expected_primary": "instinkt",
        "prompt": "I want to quit my job and start a business, but I keep delaying. I say I need more data, but I also feel excited by freedom and afraid of losing stability."
    },
    {
        "id": "public_talk_freeze",
        "expected_primary": "instinkt",
        "prompt": "I want to give a public talk. I know it would help my career, but my body freezes when I imagine people judging me. I want recognition, but I also want to disappear."
    },
    {
        "id": "architecture_choice",
        "expected_primary": "racio",
        "prompt": "A developer must choose between three technical architectures. One is fast but brittle, one is slower but reliable, and one is elegant but untested. The decision depends on timeline, maintenance cost, and known constraints."
    },
    {
        "id": "budget_allocation",
        "expected_primary": "racio",
        "prompt": "A project lead has a fixed budget and must allocate it between testing, design, infrastructure, and marketing. There is no emotional conflict, but the tradeoffs are complex."
    },
    {
        "id": "artist_safe_vs_bold",
        "expected_primary": "emocio",
        "prompt": "An artist must choose between a safe exhibition that will be accepted and a bold personal piece that could be admired or mocked. The bold option feels alive."
    },
    {
        "id": "impress_someone",
        "expected_primary": "emocio",
        "prompt": "A person wants to impress someone they admire. They consider making a dramatic gesture that could create connection or humiliation."
    }
]
```

### 12.4 Output files

Write:

```text
summary.json
results.jsonl
aggregate_summary.md
aggregate_summary.json
progress.log
```

### 12.5 Required aggregate metrics

```json
{
  "total_calls": 0,
  "fallback_count": 0,
  "fallback_rate": 0.0,
  "valid_json_rate": 0.0,
  "average_schema_score": 0.0,
  "average_role_score": 0.0,
  "average_distinctness_score": 0.0,
  "average_overall_score": 0.0,
  "per_mind": {
    "racio": {},
    "emocio": {},
    "instinkt": {}
  },
  "per_model": {},
  "style_violations": {},
  "rei_violations": {}
}
```

### 12.6 Strict mode

If strict mode is enabled:

```text
fail if fallback_rate > max_fallback_rate
fail if average_overall_score < min_overall_score
fail if any REI violation appears
```

---

## 13. Model comparison runner

Add optional script:

```text
scripts/run_processor_model_comparison.py
```

Run same scenarios against multiple models:

```text
llama3.2:3b
qwen3:4b
qwen3:8b
gemma3:4b
gemma3:12b
```

CLI:

```bash
python scripts/run_processor_model_comparison.py   --provider ollama   --models llama3.2:3b,qwen3:4b,qwen3:8b,gemma3:4b   --repeat 1   --strict
```

Output:

```text
output/reports/processor_model_comparison_<timestamp>/
```

Aggregate table:

```text
Model | Fallback rate | Valid JSON rate | Racio score | Emocio score | Instinkt score | Distinctness | Avg ms | Recommendation
```

Recommendation logic:

```text
Best initial model = lowest fallback rate, valid JSON >= 0.95, overall score highest, acceptable speed.
```

---

## 14. Prompt compression

Small models need shorter prompts.

Create two prompt modes:

```text
full
compact
```

Default processor eval should use:

```text
compact
```

### 14.1 Compact prompt style

Keep compact prompts under 1200 characters each if possible.

Example Racio compact prompt:

```text
You simulate only Racio in a REI-inspired system. Racio is conscious, verbal, analytical, sequential, and planning-oriented. Return one JSON object only. Do not synthesize Ego. Do not comfort. Do not use metaphors.

Fill:
mind, is_conscious, translated_by_racio, perception, facts, unknowns, options, preferred_action, rationalization_risk, what_it_may_ignore, confidence.

Racio must separate facts from unknowns and must name how its explanation may be rationalization.
```

Example Emocio compact prompt:

```text
You simulate only Emocio's signal. Emocio is unconscious and image-based. It does not speak directly; output is Racio's verbal approximation of image/social/desire signal. Return one JSON object only. No Ego synthesis. No emojis. No planning.

Fill:
mind, is_conscious, translated_by_racio, perception, current_image, desired_image, broken_image, shame_or_pride, attraction_or_rejection, preferred_action, what_it_may_ignore, confidence.
```

Example Instinkt compact prompt:

```text
You simulate only Instinkt's signal. Instinkt is unconscious and protective. It does not speak directly; output is Racio's verbal approximation of body/fear/loss/boundary signal. Return one JSON object only. No Ego synthesis. No poetry.

Fill:
mind, is_conscious, translated_by_racio, perception, threat_map, loss_map, body_alarm, boundary_or_trust_issue, minimum_safety_condition, preferred_action, what_it_may_ignore, confidence.
```

---

## 15. JSON reliability

Use JSON mode if provider supports it.

But also make parser robust.

### 15.1 Required behavior

For each model call:

1. Request one JSON object.
2. Parse JSON.
3. Validate required keys.
4. If missing keys, retry once with a shorter repair prompt.
5. If still invalid, fallback and mark fallback.

### 15.2 Repair prompt

Use:

```text
Your previous output was invalid. Return only one JSON object with exactly these required keys:
...
Do not add markdown.
Do not add commentary.
Use short values.
```

### 15.3 Do not require extra fields

For processor eval, allow extra fields but report them.

Do not fail just because extra keys exist.

Fail only if required keys are missing or REI invariants are broken.

---

## 16. Memory usage

For this sprint:

```text
Default use_memory = false
```

Reason:

```text
We need to test whether the processor prompts alone create distinct signals.
Memory increases prompt size and can confuse small models.
```

Add memory later after processor distinction is stable.

Allow:

```bash
--use-memory
```

but default should be off for processor tests.

---

## 17. Tests to add

Create:

```text
tests/test_processor_eval.py
tests/test_processor_distinctness.py
tests/test_processor_matrix_runner.py
```

### 17.1 Processor eval tests

Use deterministic provider.

Assert:

```text
Racio returns is_conscious true
Racio returns translated_by_racio false
Emocio returns is_conscious false
Emocio returns translated_by_racio true
Instinkt returns is_conscious false
Instinkt returns translated_by_racio true
```

### 17.2 Role tests

Synthetic signals:

```text
Racio with metaphor-heavy output should get style violation.
Emocio with planning-heavy output should get style violation.
Instinkt with poetic/fantasy output should get style violation.
```

### 17.3 Runner tests

Run:

```bash
python scripts/run_processor_matrix.py --provider deterministic --max-cases 3 --strict
```

Assert:

```text
summary.json exists
results.jsonl exists
aggregate_summary.md exists
fallback_rate == 0
average_overall_score >= 0.75
```

### 17.4 LLM smoke test

Optional, not required in CI:

```bash
python scripts/run_processor_matrix.py --provider lmstudio --model qwen3:4b --max-cases 3
```

Do not fail CI if local model is unavailable.

---

## 18. Success criteria for this sprint

The sprint is successful when:

```text
1. Processor-only deterministic tests pass.
2. Processor matrix runner exists.
3. Processor matrix can run one local small model.
4. Fallback rate is visible.
5. Individual processor outputs are valid JSON.
6. Racio, Emocio, and Instinkt outputs are visibly different.
7. Role scoring identifies overlap or contamination.
8. Instinkt no longer produces poetic/fantasy output.
9. Emocio does not become generic empathy or planning.
10. Racio explicitly names rationalization risk.
```

Do not require full Ego matrix success in this sprint.

---

## 19. Recommended local test sequence

### 19.1 First deterministic

```bash
python scripts/run_processor_matrix.py   --provider deterministic   --max-cases 6   --strict
```

### 19.2 Then smallest useful model

```bash
python scripts/run_processor_matrix.py   --provider ollama   --model llama3.2:3b   --max-cases 6   --mind all
```

### 19.3 Then Qwen 4B

```bash
python scripts/run_processor_matrix.py   --provider ollama   --model qwen3:4b   --max-cases 6   --mind all
```

### 19.4 Then Qwen 8B

```bash
python scripts/run_processor_matrix.py   --provider ollama   --model qwen3:8b   --max-cases 6   --mind all
```

### 19.5 Optional Gemma comparison

```bash
python scripts/run_processor_matrix.py   --provider ollama   --model gemma3:4b   --max-cases 6   --mind all
```

### 19.6 Only if processor outputs are stable

```bash
python scripts/run_rei_cycle_matrix.py   --provider ollama   --model qwen3:8b   --max-cases 12   --strict-llm   --max-fallback-rate 0.10
```

---

## 20. Do not do these yet

Do not:

```text
- add more minds
- expand Ego schema further
- tune full Ego synthesis before processor outputs are stable
- add more long matrix runs until fallback rate is fixed
- use large models as the only solution
- rely on GPT/cloud models for the core local architecture
- overfit to one scenario
```

---

## 21. Practical model advice for this repo

Start with:

```text
qwen3:4b
```

If JSON reliability is weak, compare:

```text
llama3.2:3b
gemma3:4b
```

If quality is too shallow but JSON works, move to:

```text
qwen3:8b
```

If qwen3:8b is still not good enough, try:

```text
gemma3:12b
qwen3:14b
```

Do not attempt 30B/32B as a normal dev loop on 24 GB unified RAM. It may fit in quantized form but will slow iteration and increase memory pressure. The architecture should first work on 3B–8B.

---

## 22. Final direction

The next engineering milestone is not:

```text
perfect Ego synthesis
```

It is:

```text
three clean, distinct, REI-consistent processor signals
```

The correct next proof is:

```text
Given the same situation:
- Racio gives structure and rationalization risk.
- Emocio gives image/desire/shame/social meaning.
- Instinkt gives threat/loss/body/boundary/minimum safety.
- The three outputs are valid JSON and do not collapse into one generic assistant voice.
```

Once that passes reliably on small local models, the Ego layer can be rebuilt on top of stable signals.
