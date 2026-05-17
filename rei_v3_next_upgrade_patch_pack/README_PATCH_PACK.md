# REI-v3 next upgrade patch pack

This package is not meant as a blind `git apply` patch. It is a structured upgrade pack for Codex or manual implementation.

## Why this upgrade exists

The current repo already has the right direction: separate REI signals, profile weights, acceptance assessment, and EgoResultant. The next problem is canon drift: Racio, Emocio, and Instinkt are currently described in several places. If those descriptions diverge, the model will slowly collapse into:

- Racio = objective reason
- Emocio = generic emotion/empathy
- Instinkt = generic fear/risk
- Ego = fourth wise judge

The canon says otherwise.

## What this pack adds

```text
knowledge/canon/
  processor_contracts.json
  source_map.json
  psi_racio.md
  psi_emocio.md
  psi_instinkt.md
  psi_ego_world_life.md
  eros_comments_rei_dynamics.md

app/backend/rei/
  contract_loader.py

tests/
  test_rei_canonical_contracts.py
  test_rei_cycle_regression_contract.py

scripts/
  verify_rei_contract_pack.py

examples/scenarios/
  same_behavior_different_origins.json
```

## Implementation order

1. Copy `knowledge/canon/*` into the repository.
2. Copy `app/backend/rei/contract_loader.py`.
3. Run:

```bash
python scripts/verify_rei_contract_pack.py
```

4. Refactor `app/backend/rei/prompts.py`:
   - Keep safety boundary text.
   - Import `build_processor_prompt`, `build_ego_prompt`, `required_keys_for`, `ego_required_keys`.
   - Replace hardcoded processor prompts with generated prompts from the contract loader.

5. Refactor `app/backend/rei/processor_contracts.py`:
   - Either remove duplicated theology or turn it into a compatibility wrapper around `contract_loader.py`.
   - Do not keep separate processor definitions there.

6. Refactor `app/backend/rei/engine.py`:
   - Remove or shrink `MIND_PROMPT_CONTRACTS`.
   - Do not hardcode mind theology in engine.
   - Use the contract loader for processor prompt contracts.
   - Keep runtime flow and safety checks.

7. Update `app/backend/rei/models.py`:
   - Add canonical fields listed in `processor_contracts.json`.
   - Add EgoResultant world-renderer fields.

8. Add tests and run your normal backend test command.

## Hard invariants

- Racio: `is_conscious=true`, `translated_by_racio=false`.
- Emocio: `is_conscious=false`, `translated_by_racio=true`.
- Instinkt: `is_conscious=false`, `translated_by_racio=true`.
- EgoResultant is not a fourth mind.
- The same visible behavior can have different processor origins.
- Do not infer real people's REI character with certainty.
