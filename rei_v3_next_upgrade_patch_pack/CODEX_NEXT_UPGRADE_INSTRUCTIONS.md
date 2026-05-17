# Codex task: REI-v3 canonical processor-contract upgrade

Repository: `kotlet13/rei-v3`
Branch: `main`

## Goal

Upgrade REI-v3 so processor ontology is source-backed and loaded from `knowledge/canon/processor_contracts.json`, instead of being duplicated across `prompts.py`, `processor_contracts.py`, and `engine.py`.

The conceptual target:

```text
Racio = conscious verbal processor of concrete order, utility, sequence, words, numbers, and explanation.
Emocio = unconscious image/social/desire/status/body-expression processor; output is Racio translation.
Instinkt = unconscious fear/body/loss/trust/boundary/attachment processor; output is Racio translation.
EgoResultant = resulting experienced world/story/action pressure, not a fourth mind.
```

## Patch assets in this pack

Copy these files into the repo:

```text
knowledge/canon/processor_contracts.json
knowledge/canon/source_map.json
knowledge/canon/psi_racio.md
knowledge/canon/psi_emocio.md
knowledge/canon/psi_instinkt.md
knowledge/canon/psi_ego_world_life.md
knowledge/canon/eros_comments_rei_dynamics.md
app/backend/rei/contract_loader.py
tests/test_rei_canonical_contracts.py
tests/test_rei_cycle_regression_contract.py
scripts/verify_rei_contract_pack.py
examples/scenarios/same_behavior_different_origins.json
```

## Required code changes

### 1. `app/backend/rei/prompts.py`

Refactor it so processor prompts are generated from `contract_loader.py`.

Expected pattern:

```python
from .contract_loader import (
    build_ego_prompt,
    build_processor_prompt,
    ego_required_keys,
    required_keys_for,
)

RACIO_SYSTEM_PROMPT = build_processor_prompt("racio", mode="full")
EMOCIO_SYSTEM_PROMPT = build_processor_prompt("emocio", mode="full")
INSTINKT_SYSTEM_PROMPT = build_processor_prompt("instinkt", mode="full")
EGO_SYSTEM_PROMPT = build_ego_prompt()

RACIO_REQUIRED_KEYS = required_keys_for("racio")
EMOCIO_REQUIRED_KEYS = required_keys_for("emocio")
INSTINKT_REQUIRED_KEYS = required_keys_for("instinkt")
EGO_REQUIRED_KEYS = ego_required_keys()

PROCESSOR_PROMPTS = {
    "racio": RACIO_SYSTEM_PROMPT,
    "emocio": EMOCIO_SYSTEM_PROMPT,
    "instinkt": INSTINKT_SYSTEM_PROMPT,
}

PROCESSOR_REQUIRED_KEYS = {
    "racio": RACIO_REQUIRED_KEYS,
    "emocio": EMOCIO_REQUIRED_KEYS,
    "instinkt": INSTINKT_REQUIRED_KEYS,
}
```

Preserve project safety rules if they are used elsewhere, but do not duplicate processor theology.

### 2. `app/backend/rei/processor_contracts.py`

Turn it into a compatibility wrapper or delete it if no longer needed.

Safe wrapper option:

```python
from .contract_loader import build_processor_prompt, required_keys_for

PROCESSOR_MINIMAL_REQUIRED_KEYS = {
    "racio": required_keys_for("racio"),
    "emocio": required_keys_for("emocio"),
    "instinkt": required_keys_for("instinkt"),
}

def processor_prompt(mind, mode="compact"):
    return build_processor_prompt(mind, mode=mode)
```

### 3. `app/backend/rei/models.py`

Add canonical base fields to `REISignal`:

```python
native_language: list[str] = Field(default_factory=list)
world_filter: str = ""
truth_model: str = ""
defense_mode: str = ""
justice_model: str = ""
non_accepting_distortion: str = ""
blind_spot: str = ""
source_refs: list[str] = Field(default_factory=list)
```

Then add mind-specific fields.

Racio:

```python
utility_model: str = ""
rationalization_target: str = ""
translation_of_other_minds_risk: str = ""
```

Emocio:

```python
recognition_need: str = ""
body_expression: str = ""
substitute_solution_risk: str = ""
```

Instinkt:

```python
fear_feeling: str = ""
trust_boundary: str = ""
attachment_loss: str = ""
scarcity_or_envy: str = ""
```

Add/confirm EgoResultant fields:

```python
perceived_world: str = ""
conscious_story: str = ""
hidden_signal_sources: dict[str, str] = Field(default_factory=dict)
trusted_mind_or_coalition: MindNameExtended = "unknown"
suppressed_mind: MindNameExtended = "unknown"
final_pressure: str = ""
action_tendency: str = ""
racio_after_story: str = ""
```

Use defaults where possible to avoid breaking older traces.

### 4. `app/backend/rei/engine.py`

Remove hardcoded theology from `MIND_PROMPT_CONTRACTS` or make it a thin reference to loaded contracts.

Do not remove:
- provider flow
- JSON repair behavior
- fallback behavior
- diagnostics
- acceptance assessment
- profile weighting

Do enforce:
- Emocio and Instinkt output are Racio translations.
- Racio must include rationalization risk.
- EgoResultant must not behave like a fourth mind.
- R=E=I must not default to Racio just because Racio is verbal.

### 5. Tests

Add the tests from this pack. Then add a smoke test around the existing REI cycle if the project already has test scaffolding for the engine.

Required semantic regression:

```text
Input: "I do not want to attend the meeting."

Expected:
- Racio origin may be utility/time/control/evidence.
- Emocio origin may be humiliation/dead scene/status wound/broken image.
- Instinkt origin may be danger/distrust/exposure/body alarm/boundary/loss.
```

The same visible behavior must not be automatically assigned to one processor.

## Acceptance criteria

- `python scripts/verify_rei_contract_pack.py` passes.
- Processor prompts are generated from `knowledge/canon/processor_contracts.json`.
- No duplicated full processor theology remains in `engine.py`.
- Emocio and Instinkt always use `translated_by_racio=true`.
- Racio always uses `translated_by_racio=false`.
- EgoResultant prompt explicitly says it is not a fourth mind.
- Tests pass.
- Existing API response remains backward-compatible where possible.
