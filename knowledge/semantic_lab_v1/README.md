# REI semantic laboratory v1

This directory is the source-grounded, reviewable semantic corpus for testing
how a conclusion is reached through Racio, Emocio or Instinkt. It is an
evaluation corpus, not a training dataset.

## Boundaries

- Slovene is the canonical semantic language; English is an operational gloss.
- A family groups all of its perturbations. Variants are never split into
  training/validation partitions.
- Character is not inferred from behavior. Native routes are profile-blind.
- Expected routes cite source claims, grounded evidence and valid option IDs.
- Generated fixture gold is deterministic and comes only from
  `canon_approved` source records.
- No model is called by the fixture builder.
- There is no SFT, LoRA or QLoRA export path.

## Source layout

```text
manifest.yaml                         corpus invariants and variant modes
schemas/                              JSON contracts
scenario_families/families.jsonl      24 reviewed source families
review/review_log.jsonl               append-only approval evidence
source_index.jsonl                    source-claim index used by the families
```

Committed generated fixtures live in
`tests/fixtures/semantic_lab_v1/`. Rebuild or verify them with:

```powershell
app\backend\.venv\Scripts\python.exe scripts\build_semantic_lab_fixtures.py
app\backend\.venv\Scripts\python.exe scripts\build_semantic_lab_fixtures.py --check
```

The builder validates source claim IDs, source paths, `SceneEvent` contracts,
option references, route IDs, review status and family grouping before writing
canonical JSON.
