# Codex kickoff — samo arhiviranje trenutne REI-v3 arhitekture

Repo: `kotlet13/rei-v3`

Najprej preberi:

`Docs/plans/REI_native_composition_architecture_upgrade_2026-07-13.md`

Izvedi samo Fazo A0 in A1 iz dokumenta.

## Obvezno

1. Preveri dejanski `HEAD` in `git status`.
2. Ne resetiraj ali prepisuj uporabnikovih sprememb.
3. Zaženi trenutni `python -m pytest -q`.
4. Ustvari reproducibilen arhiv:
   `archive/rei_v3_text_llm_baseline_2026-07-13/`
5. Dodaj:
   - `scripts/archive_rei_architecture.py`
   - `README.md`
   - `ARCHITECTURE.md`
   - `BASELINE_VERIFICATION.md`
   - `SOURCE_COMMIT`
   - `MANIFEST.json`
   - `FILES.sha256`
   - snapshot aktivne stare arhitekture
6. Arhiviraj trenutno:
   - `app/backend/rei/`
   - `app/gui/`
   - `scripts/`
   - `tests/` kot `reference_tests/`
   - `knowledge/`
   - sledene dataset metapodatke
   - `Docs/evals/`
   - `Docs/plans/`
   - `README.md`, `CURRENT.md`, `.gitignore`
7. Ne kopiraj:
   - obstoječega `archive/`
   - `output/`
   - cache, logov, modelov, `.venv`
   - lokalnih prompt overrideov
8. Izračunaj in preveri SHA-256 vseh arhivskih datotek.
9. Dodaj pytest exclusion za `archive/`.
10. Dodaj test, da aktivna koda ne uvaža arhiva.
11. `Docs/plans/REI_v3_Codex_first_execution_prompt.md` označi kot `SUPERSEDED` in kopiraj v arhiv.
12. Ne dodajaj nove arhitekture in ne spreminjaj trenutnega runtime vedenja.

## Commit

Pripravi samo:

`chore(archive): freeze textual REI-v3 architecture before native-modalities rewrite`

Po tem commitu se ustavi.

## Poročilo

Navedi:

- source SHA;
- git diff povzetek;
- arhivirane poti;
- izključene poti;
- hash verification;
- testne rezultate;
- morebitne omejitve reprodukcije;
- odprta vprašanja;
- točen commit SHA.
