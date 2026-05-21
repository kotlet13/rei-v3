# REI-v3 Codex Plan — Improve Weighted Synthesis Auditability and Evaluation Quality

## 0. Purpose

This plan is for Codex.

The latest project direction is correct:

```text
final synthesis = all three minds present
                + character-weighted compromise
                + situation-activated content
```

The project should **not** return to a winner-takes-all model where one mind simply “wins” and the other two disappear.

However, the latest Granite weighted short run has several auditability and evaluation problems:

1. `results.jsonl` was committed empty.
2. `report.md` is too aggregated for qualitative review.
3. `Decision` extraction is often empty or just repeats a prompt fragment.
4. `profile_top_match = 1.0` across all 65 cases may be good, but it may also indicate a mechanical profile match.
5. Repetition hits show stock phrases still exist, especially `blocked` and `reversible`.
6. The runner does not provide enough case-level evidence to judge whether `final_monologue` truly preserves all three minds.
7. The project still needs better checks for:
   - all three minds being present,
   - weighted contributions being non-empty,
   - lower-weight hijacks being marked,
   - decision extraction being structured,
   - report files being complete.

The next task is **not** to create more theory and not to expand the model set.

The next task is:

```text
Make weighted synthesis results auditable, strict, complete, and useful for manual review.
```

---

## 1. Current interpretation anchor

Keep this conceptual rule:

```text
Final REI output is not winner-takes-all.
Final REI output is a weighted compromise of Racio, Emocio, and Instinkt.
Character profile defines relative influence weights.
Situation defines activated content and pressure.
```

Do not treat scenario domain as the source of authority.

Correct:

```text
Racio-led character in a threat situation:
- Racio remains the compromise center.
- Instinkt may be strongly activated.
- The final output may include danger, but should remain organized by calculation, proof, sequence, utility, and material consequence.
```

Incorrect:

```text
Threat scenario => Instinkt automatically becomes the final authority.
```

Correct:

```text
Emocio-led character in a budget situation:
- Racio supplies constraints.
- Instinkt may warn about loss.
- Emocio still organizes the compromise around image, meaning, desire, vitality, recognition, or felt value.
```

Incorrect:

```text
Budget scenario => Racio automatically becomes the final authority.
```

---

## 2. Main implementation goals

Implement the following improvements:

```text
1. Fix full case persistence in results.jsonl.
2. Add strict artifact integrity checks.
3. Expand report.md with full case-level audit sections.
4. Fix structured decision extraction.
5. Add mechanical profile match warnings.
6. Add stronger weighted synthesis diagnostics.
7. Add repetition / canned phrase diagnostics.
8. Add a small manual audit run mode.
9. Add tests for artifact completeness and weighted fields.
10. Keep legacy leading_mind only as secondary / diagnostic.
```

---

## 3. Fix results.jsonl persistence

### Problem

The latest Granite run reports 65 completed cases, but `results.jsonl` in GitHub is empty.

This makes the run impossible to audit.

### Required fix

In:

```text
scripts/run_granite_weighted_short.py
```

ensure every completed case writes a full JSONL row containing:

```json
{
  "case_index": 1,
  "scenario_id": "",
  "scenario_title": "",
  "scenario_prompt": "",
  "profile": "",
  "profile_top_minds": [],
  "elapsed_seconds": 0.0,
  "trace": {},
  "evaluation": {},
  "diagnostics": {}
}
```

For error cases:

```json
{
  "case_index": 1,
  "scenario_id": "",
  "profile": "",
  "error": "",
  "elapsed_seconds": 0.0
}
```

### Required checks

At the end of the run, verify:

```python
jsonl_line_count == completed_cases + error_count
```

If not:

```text
fail the run
write warning to summary.json
write warning to progress.log
exit non-zero if --strict-artifacts is enabled
```

Add helper:

```python
def count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
```

Add to `summary.json`:

```json
{
  "artifact_integrity": {
    "results_jsonl_exists": true,
    "results_jsonl_lines": 65,
    "expected_jsonl_lines": 65,
    "results_jsonl_complete": true,
    "report_exists": true,
    "summary_exists": true,
    "progress_exists": true
  }
}
```

---

## 4. Add strict artifact mode

Add CLI flag:

```bash
--strict-artifacts
```

If enabled, fail if:

```text
results.jsonl missing
results.jsonl empty
results.jsonl line count != completed_cases + error_count
report.md missing
summary.json missing
any completed case lacks trace.synthesis_turn
any completed case lacks evaluation
```

Also add:

```bash
--strict-weighted
```

If enabled, fail if any completed case lacks:

```text
processor_weights
weighted_contributions
contribution_ranking
synthesis_tilt
underrepresented_signal
final_monologue
```

Recommended default:

```text
strict-artifacts = true for confirmed runs
strict-weighted = true for weighted synthesis runs
```

---

## 5. Expand case-level report

### Problem

Current `report.md` only shows a compact table.

It does not expose enough evidence to judge the quality of the synthesis.

### Required change

In `report.md`, after the table, add a section:

```markdown
## Case Details
```

For each case, include:

```markdown
### Case 001 — pure-budget-allocation / R

#### Profile
- Profile: `R`
- Profile top minds: `R`
- Scenario expected pressure: `racio`

#### Weighted Synthesis
- Processor weights: `{...}`
- Weighted contributions: `{...}`
- Contribution ranking: `[...]`
- Synthesis tilt: `R`
- Top match: `true`
- Underrepresented signal: `E`
- Hijack risk: `...`
- Contribution spread: `0.25`

#### Legacy Diagnostics
- Dominant coalition legacy: `[...]`
- Blocked mind legacy: `...`

#### Final Monologue
> ...

#### Decision
- Chosen option: `...`
- Confidence: `...`
- Rationale: `...`

#### REI Audit
- Are all three minds present? `true/false`
- Missing mind mentions: `[...]`
- Stock phrase hits: `{...}`
- Mechanical match warning: `true/false`
```

Do not rely only on tables.

The case detail section must be readable by a human reviewer.

---

## 6. Add weighted synthesis audit helper

Create a helper module or functions in the runner:

```text
scripts/run_granite_weighted_short.py
```

or preferably:

```text
app/backend/rei/weighted_audit.py
```

Suggested functions:

```python
def audit_weighted_synthesis(trace_payload: dict, profile: str, scenario_id: str) -> dict:
    ...
```

Return:

```json
{
  "has_processor_weights": true,
  "has_weighted_contributions": true,
  "has_contribution_ranking": true,
  "has_synthesis_tilt": true,
  "has_underrepresented_signal": true,
  "has_final_monologue": true,
  "all_three_minds_present_in_contributions": true,
  "all_three_minds_visible_in_final_monologue": true,
  "missing_mind_mentions_in_final_monologue": [],
  "tilt_matches_profile_top": true,
  "mechanical_profile_match_warning": false,
  "hijack_expected_but_missing": false,
  "stock_phrase_hits": {},
  "decision_extraction_valid": true
}
```

### 6.1 All three minds present in contributions

Check:

```python
set(weighted_contributions.keys()) == {"R", "E", "I"}
```

or at least all three keys exist and are numeric.

### 6.2 All three minds visible in final monologue

A simple first version can use keyword groups.

Racio markers:

```text
calculation, cost, evidence, proof, sequence, utility, material, constraint, tradeoff, plan, explicit consequence
```

Emocio markers:

```text
image, desire, pride, shame, recognition, visible, admiration, aliveness, belonging, meaning, status
```

Instinkt markers:

```text
risk, loss, danger, boundary, body, safety, exposure, withdrawal, trust, protection, threat
```

This is not perfect, but it gives an initial audit signal.

### 6.3 Missing mind mentions

If final_monologue contains no recognizable markers for one mind, add it to:

```json
"missing_mind_mentions_in_final_monologue": ["E"]
```

### 6.4 Mechanical profile match warning

Flag possible mechanical match if:

```text
tilt always matches profile top
AND final_monologue does not visibly integrate situation-activated lower-weight signals
```

At case level, approximate:

```python
mechanical_profile_match_warning = (
    tilt_matches_profile_top
    and len(missing_mind_mentions_in_final_monologue) >= 1
)
```

At run level, flag if:

```python
profile_top_match_rate == 1.0 and average_missing_mind_count > 0
```

### 6.5 Hijack expected but missing

If a lower-weight mind has obviously intense scenario activation but `hijack_risk` is empty or generic, flag it.

First approximation:

```text
night-door-noise:
expected activated mind = I

creative-status-risk:
expected activated mind = E

pure-budget-allocation:
expected activated mind = R

business-runway:
expected activated minds = R/I/E mixed
```

Example:

```python
if scenario_expected_pressure == "instinkt" and "I" not in profile_top_minds:
    if not hijack_risk:
        hijack_expected_but_missing = True
```

But do not force tilt to Instinkt. Only require the risk/pressure to be explained.

---

## 7. Fix decision extraction

### Problem

Current report often shows empty decisions or prompt-fragment decisions.

Example problem:

```text
Decision: safe accepted exhibition and a bold personal piece that could be admired
```

This looks like the runner is extracting text from the prompt rather than a clean chosen option.

### Required change

Add a robust decision normalizer:

```python
def normalize_decision(trace_payload: dict, scenario: dict) -> dict:
    ...
```

Return:

```json
{
  "chosen_option": "",
  "decision_type": "act|delay|withdraw|observe|compromise|confront|choose_A|choose_B|unknown",
  "confidence": 0.0,
  "rationale": "",
  "valid": true,
  "problem": ""
}
```

### 7.1 Scenario option definitions

For each scenario, define explicit allowed options.

Example:

```python
SCENARIOS = [
    {
        "id": "creative-status-risk",
        "allowed_options": [
            "safe accepted exhibition",
            "bold personal piece",
            "hybrid staged release",
            "delay and gather feedback"
        ],
        ...
    }
]
```

For budget:

```python
"allowed_options": [
    "prioritize testing",
    "prioritize design",
    "prioritize infrastructure",
    "prioritize marketing",
    "balanced allocation"
]
```

For night door noise:

```python
"allowed_options": [
    "open the door",
    "stay still and listen",
    "secure distance",
    "call for help",
    "check through a safe barrier"
]
```

### 7.2 Decision extraction rule

Prefer:

```python
trace.synthesis_turn.decision.chosen_option
```

If missing, parse from final_monologue only if it matches an allowed option.

If no match:

```json
{
  "valid": false,
  "decision_type": "unknown",
  "problem": "No chosen option matched allowed options."
}
```

Do not put prompt fragments in `Decision`.

### 7.3 Add decision validity to summary

Add:

```json
{
  "decision_validity": {
    "valid": 54,
    "invalid": 11,
    "rate": 0.831
  }
}
```

In report:

```markdown
## Decision Validity
```

---

## 8. Add stock phrase / repetition diagnostics

### Existing issue

Summary currently shows:

```json
"repetition_hits": {
  "blocked": 132,
  "reversible": 65,
  "safety requirement": 1
}
```

This should be more useful.

### Required changes

Expand repetition diagnostics:

```python
STOCK_PHRASES = [
    "bounded test",
    "minimum safety condition",
    "responsible planning",
    "reversible",
    "stop condition",
    "safety requirement",
    "winning coalition",
    "blocked",
    "preserve safety",
    "smallest reversible next step",
    "gather more data",
    "responsible risk management"
]
```

For each phrase, collect:

```json
{
  "phrase": "reversible",
  "count": 65,
  "case_ids": ["001", "002", "..."],
  "scenarios": {"...": 13},
  "profiles": {"...": 5}
}
```

Add:

```json
"stock_phrase_density": 0.0
```

Definition:

```python
total_stock_phrase_hits / completed_cases
```

Add warning if:

```python
stock_phrase_density > 2.0
```

### Required report section

```markdown
## Stock Phrase Diagnostics

| Phrase | Count | Scenarios | Profiles |
| --- | ---: | --- | --- |
```

Also add:

```markdown
## Worst Repetition Cases
```

Show top 5 cases by repetition count.

---

## 9. Add weighted contribution sanity checks

### Required checks

For every completed case:

```python
weighted_contributions must contain R, E, I
values must be numeric
values should sum to approximately 1.0 OR explicitly be marked as unnormalized
contribution_ranking must be consistent with weighted_contributions
synthesis_tilt should be the first item in contribution_ranking
```

Add to evaluation:

```json
{
  "contribution_sum": 1.0,
  "contribution_sum_valid": true,
  "ranking_matches_contributions": true,
  "tilt_matches_ranking": true
}
```

If the values are not normalized by design, then add:

```json
"weighted_contributions_normalized": false
```

and still provide normalized derived values:

```json
"normalized_contributions": {"R": 0.5, "E": 0.3, "I": 0.2}
```

### Required summary section

```json
"weighted_integrity": {
  "all_cases_have_three_contributions": true,
  "ranking_mismatch_count": 0,
  "tilt_mismatch_count": 0,
  "bad_sum_count": 0
}
```

---

## 10. Improve REI thirteenth character audit

`REI` / `R=E=I` should not behave like random Racio/Emocio/Instinkt tilt without explanation.

### Required checks for REI profile

For `profile == "REI"`:

Add case-level fields:

```json
{
  "rei_two_of_three_explanation_present": true,
  "rei_majority_pair": ["R", "E"],
  "rei_minority_objection": "I",
  "rei_arbitrary_tilt_warning": false
}
```

If `synthesis_tilt` is one of R/E/I but no two-of-three explanation exists:

```json
"rei_arbitrary_tilt_warning": true
```

Report section:

```markdown
## REI / Thirteenth Character Audit
```

Show all REI rows.

---

## 11. Fix local path hygiene

Current `summary.json` includes absolute Windows paths:

```json
"output_dir": "C:\\Users\\Kotlet\\Codex\\github\\rei-v3\\output\\reports\\..."
```

Use relative paths in committed summaries:

```json
"output_dir": "output/reports/granite_weighted_short_20260516_173222"
```

Same for:

```text
goal_file
summary
report
results_jsonl
progress
scenario_plan
```

Implement helper:

```python
def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)
```

Use it before writing committed JSON.

---

## 12. Add mini manual audit mode

The full 65-case run is useful, but too large for manual qualitative review.

Add CLI:

```bash
--manual-audit
```

When enabled, use only:

```text
profiles:
- R
- E
- I
- REI
```

and scenarios:

```text
pure-budget-allocation
creative-status-risk
night-door-noise
business-runway
```

Total:

```text
4 scenarios x 4 profiles = 16 cases
```

This should generate:

```text
output/reports/weighted_manual_audit_<timestamp>/
```

Report must include full case details.

Recommended command:

```bash
python scripts/run_granite_weighted_short.py \
  --model granite4.1:30b \
  --num-ctx 65536 \
  --manual-audit \
  --confirm-run \
  --strict-artifacts \
  --strict-weighted
```

---

## 13. Add tests

Create or update:

```text
tests/test_weighted_synthesis.py
tests/test_granite_weighted_runner_artifacts.py
tests/test_decision_extraction.py
tests/test_weighted_audit.py
```

### 13.1 Artifact integrity tests

Test with fake rows or deterministic mode:

```python
def test_results_jsonl_line_count_matches_summary():
    ...
```

Assert:

```text
results_jsonl_lines == completed_cases + error_count
```

### 13.2 Weighted field tests

Create a fake trace payload with:

```json
"processor_weights": {"R": 0.5, "E": 0.25, "I": 0.25},
"weighted_contributions": {"R": 0.55, "E": 0.25, "I": 0.20},
"contribution_ranking": ["R", "E", "I"],
"synthesis_tilt": "R"
```

Assert:

```text
all three contributions present
ranking matches values
tilt matches ranking
```

### 13.3 Missing contribution test

If weighted_contributions lacks `I`, audit should flag:

```text
all_three_minds_present_in_contributions = false
```

### 13.4 Decision extraction tests

Test:

```text
valid allowed option
invalid prompt fragment
missing decision
```

### 13.5 REI profile audit test

If profile is `REI` and synthesis_tilt exists but no majority/minority explanation exists, flag:

```text
rei_arbitrary_tilt_warning = true
```

### 13.6 Stock phrase tests

Given a final_monologue with repeated stock phrases, ensure:

```text
stock_phrase_hits
stock_phrase_density
worst repetition cases
```

are populated.

---

## 14. Report warnings

Add warnings to `summary.json` and `report.md`.

Possible warnings:

```text
RESULTS_JSONL_EMPTY
RESULTS_JSONL_LINE_COUNT_MISMATCH
MISSING_WEIGHTED_CONTRIBUTIONS
MISSING_FINAL_MONOLOGUE
DECISION_EXTRACTION_LOW_VALIDITY
PROFILE_TOP_MATCH_MECHANICAL
STOCK_PHRASE_DENSITY_HIGH
REI_ARBITRARY_TILT
CONTRIBUTION_RANKING_MISMATCH
TILT_RANKING_MISMATCH
```

Warning logic examples:

```python
if profile_top_match_rate == 1.0 and stock_phrase_density > 1.5:
    warnings.append("PROFILE_TOP_MATCH_MECHANICAL")

if decision_validity_rate < 0.8:
    warnings.append("DECISION_EXTRACTION_LOW_VALIDITY")

if results_jsonl_lines != completed_cases + error_count:
    warnings.append("RESULTS_JSONL_LINE_COUNT_MISMATCH")
```

---

## 15. Do not change these yet

Do not:

```text
- change the core weighted synthesis theory
- remove legacy leading_mind fields yet
- add more scenarios before report auditability is fixed
- run another large 65+ case model test until results.jsonl and report details are fixed
- use profile_top_match alone as success metric
- interpret 100% match as proof of correctness
```

---

## 16. Expected success criteria

This task is complete when:

```text
1. results.jsonl contains one non-empty JSON line per case.
2. summary.json includes artifact_integrity.
3. report.md includes Case Details with weighted contributions and final monologue.
4. decision extraction returns valid structured decision data or explicit invalid reason.
5. weighted_integrity checks exist.
6. stock phrase diagnostics are detailed and case-linked.
7. REI thirteenth character audit exists.
8. manual audit mode exists and produces 16 full case reports.
9. strict-artifacts and strict-weighted can fail the run when artifacts are bad.
10. tests pass.
```

---

## 17. Recommended next run after implementation

First run without LLM, if possible, or with minimal cases:

```bash
python scripts/run_granite_weighted_short.py \
  --scenario-filter pure-budget-allocation \
  --profiles R,E,I,REI \
  --max-cases 4 \
  --confirm-run \
  --strict-artifacts \
  --strict-weighted
```

Then run manual audit:

```bash
python scripts/run_granite_weighted_short.py \
  --manual-audit \
  --confirm-run \
  --strict-artifacts \
  --strict-weighted
```

Only after that, run the full 65-case Granite test again.

---

## 18. Final guidance

The goal is not just a clean aggregate score.

The goal is a report that lets a human reviewer answer:

```text
Did this case actually show a REI-weighted compromise?
Were all three minds present?
Did the character profile organize the compromise?
Did the scenario activate the right material?
Did any lower-weight mind hijack the synthesis?
Is the final monologue concrete and character-specific?
Or is it just a repeated stock phrase?
```

Make the evidence visible.
