# Codex kickoff — G3 semantična adjudikacija brez novih modelnih klicev

> **STATUS: HISTORICAL — COMPLETED / DO NOT EXECUTE**
>
> G3A adjudikacija je bila izvedena. Ta dokument ostaja samo kot provenance
> opravljenega pregleda in ne določa trenutne veje ali naslednje faze.

Repozitorij: `kotlet13/rei-v3`

Aktivna veja:

`codex/racio-gemma4-epistemic-interpreter`

Najprej preberi:

`plans/REI_post_G3_completion_plan_2026-07-17.md`

Izvedi samo **Fazo G3A — človeško-semantična adjudikacija G3**.

## Obseg

Preglej:

- vseh 8 action mismatchov;
- vseh 15 unsupported motive overclaimov;
- 6 primerov brez motive overclaimov;
- vseh 8 slovensko-angleških parov.

Uporabi samo že commitane artefakte pod:

`Docs/evals/semantic_lab_v1/g3-gemma4-racio-epistemic-2026-07-17/`

in G3 poročilo:

`Docs/evals/research_reset_2026-07/gemma4_racio_epistemic_dev_screen.md`

## Za action mismatch zapiši

- vidno manifestacijo;
- expected subtype;
- model subtype;
- expected family;
- model family;
- ali gre za:
  - true model error;
  - acceptable sibling;
  - acceptable parent;
  - gold too narrow;
  - taxonomy-level mismatch;
  - bilingual drift;
  - packet ambiguity.

Posebej razčisti:

- H1 EN `approach` proti `connect`;
- H15 `protect` proti `set_boundary`;
- H7 `seek_safety` proti `set_boundary`;
- R1 SL `conserve` proti `attack`;
- R5 SL `seek_attachment` proti `perform`.

## Za motive overclaim zapiši

- hipotezo;
- citirane observations;
- direct support yes/no;
- contextual plausibility yes/no;
- ali je nastala samo iz action labela;
- odnos do golda: same/parent/child/sibling/unrelated;
- končno klasifikacijo.

## Simetrični pregled

Obvezno preglej tudi:

- H11 SL;
- R5 EN;
- oba H15 motiva;
- R1 SL unknown preservation;
- najmanj dva partially-supported primera brez action napake.

## Bilingual analiza

Izpiši posebej:

- SL action family support;
- EN action family support;
- SL action subtype support;
- EN action subtype support;
- SL overclaim count;
- EN overclaim count.

Oceni tri možne razlage:

1. Gemma slabše razume slovenske action descriptions;
2. angleščina spodbuja več motivnega naštevanja;
3. trenutna action/motive taksonomija je preveč ravna.

## Predlagana, vendar še ne implementirana taksonomija

V poročilu oceni smiselnost družin:

```text
approach_engage
protection_regulation
confrontation
execution_expression
```

Ne spreminjaj kode ali golda.

## Output

Ustvari samo:

`Docs/evals/research_reset_2026-07/g3_semantic_adjudication.md`

Na koncu dodaj točen decision block:

```text
ACTION_TAXONOMY_DECISION:
MOTIVE_MINIMALITY_DECISION:
BILINGUAL_INPUT_DECISION:
G3_RERUN_ALLOWED: yes/no
SHADOW_INTEGRATION_ALLOWED: yes/no
V3_CONTRACT_ALLOWED: yes/no
```

## Prepovedi

- 0 modelnih klicev;
- ne spreminjaj providerja;
- ne spreminjaj prompta;
- ne spreminjaj evaluatorja;
- ne spreminjaj G3 artefaktov;
- ne izračunaj agregatnega semantic scorea;
- ne začenjaj G4;
- ne integriraj runtimea;
- ne odpiraj PR-ja;
- ne mergaj.

## Testi

Ker je faza dokumentacijska:

```powershell
git diff --check
python -m pytest tests/evaluation/test_racio_gemma4_epistemic_dev.py -q
```

Če konkretna testna pot ne obstaja, uporabi najmanjši že obstoječi focused G3 evaluator test in točno zapiši ukaz.

## Commit

`docs(eval): adjudicate G3 action and motive semantics`

Pushaj samo trenutno feature vejo in se ustavi.
