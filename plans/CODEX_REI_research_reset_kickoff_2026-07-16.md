# Codex kickoff — REI raziskovalni reset in štirislikovni Emocio screen

Repozitorij: `kotlet13/rei-v3`

Ta uporabnikova zahteva izrecno nadomešča trenutno `AGENTS.md` pravilo, ki zahteva
neposredno delo na `main`.

Najprej preberi:

`plans/REI_research_reset_human_signal_2026-07-16.md`

Izvedi samo:

```text
R0 — raziskovalni reset in vrnitev nadzora
X1 — štirislikovni Emocio exploratory screen
```

Po X1 se ustavi.

## Obvezni Git tok

```powershell
git fetch origin --prune --tags
git switch main
git pull --ff-only origin main
git status --short
git rev-parse HEAD
git log --oneline -12
```

Pričakovani HEAD je:

`5c53cad56f47e9d1f672038cd6bc2741e449de88`

Če je drugačen, zapiši dejanski SHA in preglej nove commite. Ne resetiraj.

Na dejanskem trenutnem mainu ustvari anotiran tag:

`rei-v3-pre-research-reset-2026-07-16`

Nato:

```powershell
git switch -c codex/research-reset-human-signal
git push -u origin codex/research-reset-human-signal
```

Ne pushaj neposredno na main.

## R0

1. Nadomesti `AGENTS.md` main-only pravilo z:
   - mandatory feature branches;
   - no direct main push;
   - user review between phases;
   - agent may not change project governance;
   - exploration before validation;
   - no automatic phase continuation.

2. Na vrh starega plana dodaj `SUPERSEDED FOR FUTURE WORK`:
   `plans/REI_next_phases_merge_semantic_architecture_2026-07-14.md`

3. Dodaj glavni reset plan v:
   `plans/REI_research_reset_human_signal_2026-07-16.md`

4. Posodobi `CURRENT.md` z realnim stanjem:
   - architecture stable;
   - research quality blocked;
   - no accepted model-backed RacioInterpreter;
   - no visual native-influence authority;
   - C5 is a bounded effect-rules engine;
   - C6 semantic motif detection remains open;
   - active next step is the four-image exploration;
   - C9 is closed.

5. Ustvari:
   `Docs/evals/research_reset_2026-07/research_log.md`

6. Zaženi samo:
   `python -m pytest tests/test_native_cutover.py tests/test_archive_boundary.py -q`
   in `git diff --check`.

7. Commit:
   `chore(research): restore feature-branch gates and human-signal workflow`

## X1

Raziskovalno vprašanje:

Ali LongCat ali OmniGen iz istega C4 source prizora izdelata dve dovolj ohranjeni,
vendar pomensko različni sliki za `enter_circle` in `remain_edge`?

Uporabi samo:

- `LongCat-Image-Edit-Turbo`
- `OmniGen-v1-diffusers`

Uporabi zamrznjeni source:

- artifact ID: `image_d1e97e56432b23038b8a01f6fdc24d42`
- PNG SHA-256:
  `72c9fec75d838f0db9a9abc71cbd86c4f4e637c8f54f05c0ea629e12e0f6da58`
- 1024 × 768
- možnosti: `enter_circle`, `remain_edge`

Izvedi točno štiri klice:

1. LongCat — enter_circle
2. LongCat — remain_edge
3. OmniGen — enter_circle
4. OmniGen — remain_edge

Prepovedano:

- best-of-N;
- dodatni seed;
- retry zaradi slabe slike;
- sprememba prompta po rezultatu;
- nov model;
- Stage 2;
- 48-cell matrix;
- nov security framework;
- copy-only venv;
- hardlink/reparse-point remediation;
- semantic authority;
- production authority;
- external-evidence authority.

Za exploration smeš uporabiti obstoječe zaupanja vredno lokalno okolje.
Zabeleži samo minimalni provenance iz glavnega plana.

Najprej ponovno uporabi obstoječa adapterja:

- `app/backend/rei/emocio/longcat_turbo_editor.py`
- `app/backend/rei/emocio/omnigen_editor.py`

Dovoljena je ena tanka skripta:

`scripts/run_rei_emocio_four_image_exploration.py`

Output:

`output/exploration/emocio_four_image_screen/{run_id}/`

Vključi:

- manifest.json
- source.png
- štiri output PNG-je
- contact_sheet.png
- review_template.md

PNG-jev ne commitaj.

Codex ne sme sam izpolniti človeškega semantičnega reviewa.

Focused testi so omejeni na eno novo testno datoteko in morajo preveriti:

- največ 4 model calls;
- no authority mutation;
- output only under `output/exploration`;
- manifest says `exploratory_no_authority=true`;
- no writes to `knowledge/`;
- no source mutation.

Commit:

`feat(explore): run bounded four-image Emocio signal screen`

Pushaj samo vejo:

`codex/research-reset-human-signal`

Po tem se obvezno ustavi.

Ne zaganjaj DINO, dodatnega seeda, novega modela ali naslednje faze.
Ne odpiraj PR-ja in ne mergaj.

Poročaj po formatu iz glavnega plana ter navedi lokalno pot do `contact_sheet.png`.
