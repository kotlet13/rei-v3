# Patch notes: next REI-v3 upgrade

## Files to add

- `knowledge/canon/processor_contracts.json`
- `knowledge/canon/source_map.json`
- `knowledge/canon/psi_racio.md`
- `knowledge/canon/psi_emocio.md`
- `knowledge/canon/psi_instinkt.md`
- `knowledge/canon/psi_ego_world_life.md`
- `knowledge/canon/eros_comments_rei_dynamics.md`
- `app/backend/rei/contract_loader.py`
- `tests/test_rei_canonical_contracts.py`
- `tests/test_rei_cycle_regression_contract.py`
- `scripts/verify_rei_contract_pack.py`
- `examples/scenarios/same_behavior_different_origins.json`

## Files to modify

- `app/backend/rei/prompts.py`
- `app/backend/rei/processor_contracts.py`
- `app/backend/rei/models.py`
- `app/backend/rei/engine.py`
- optional: frontend trace display if it expects old fields only

## Migration risk

Main risk: older Pydantic models may reject new LLM keys because `extra="forbid"` is used in project models. Add the new fields before switching prompts to require them.

Recommended migration order:

1. Add contract files and loader.
2. Add new optional/default fields to models.
3. Add tests.
4. Refactor prompts.
5. Refactor engine.
6. Run smoke test with deterministic provider first.
7. Run live LLM smoke test second.

## Do not do

- Do not make Ego a fourth agent.
- Do not let Emocio produce generic supportive empathy.
- Do not let Instinkt become generic business risk analysis.
- Do not let Racio claim objective truth.
- Do not hardcode a second copy of processor definitions after this migration.
