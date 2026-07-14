# SUPERSEDED

Ta dokument pripada opuščeni canonical-v2/QLoRA smeri.
Aktivna arhitektura je REI Native Composition.
Glej:

- `Docs/architecture/REI_NATIVE_COMPOSITION_ARCHITECTURE.md`
- `plans/REI_native_composition_architecture_upgrade_2026-07-13.md`
- `Docs/evals/rei_native_architecture_acceptance_2026-07-13.md`

---

# Prva izvedbena naloga za Codex - REI canonical v2

Preglej dokument `REI_v3_Codex_canonical_v2_QLoRA_plan_2026-07-10.md` in izvedi samo **Fazo 0** ter **Fazo 1**.

## Obvezni cilji

1. Zamrzni in dokumentiraj trenutni legacy baseline brez spremembe runtime vedenja.
2. Posodobi `CURRENT.md` in `README.md`, da jasno ločita:
   - legacy 156-case baseline,
   - aktivni GUI/dataset workbench,
   - načrtovani canonical-v2 engine.
3. Dodaj:
   - `knowledge/canon/claims_v2.jsonl`
   - `knowledge/canon/processors_v2.yaml`
   - `knowledge/canon/character_rules_v2.yaml`
   - `knowledge/canon/open_questions_v2.md`
   - `knowledge/glossary/rei_terms_v2.yaml`
4. Za vsak začetni core claim zapiši:
   - stabilen `claim_id`;
   - slovensko kanonično besedilo;
   - angleški operativni gloss;
   - `kind` (`OD`, `EK`, `IZ`);
   - `status`;
   - `scope`;
   - `source_file`;
   - stran oziroma dokument;
   - `risk_class`;
   - prevajalsko opombo, kadar je potrebna.
5. `Docs/REI_weighted_synthesis_working_note.md` označi kot delno preseženo implementacijsko hipotezo. Ne briši ga.
6. Novi kanon ne sme vsebovati konkretnih benchmarkskih pravil o:
   - quit-job;
   - runway;
   - side-hustle;
   - revenue milestone;
   - first business-change scenario.
7. Dodaj validator in teste, ki preverijo:
   - source traceability;
   - obvezno slovensko kanonično besedilo;
   - ločen angleški gloss;
   - status in risk class;
   - odsotnost scenario-specific pravil v core processor canon.
8. V tej nalogi ne spreminjaj:
   - `app/backend/rei/engine.py`;
   - `app/backend/rei/profiles.py`;
   - `app/backend/rei/acceptance.py`;
   - trenutnega runtime prompt vedenja.
9. Zaženi celoten testni paket.
10. Na koncu poročaj:
    - kratek `git diff` povzetek;
    - seznam novih/spremenjenih datotek;
    - rezultate testov;
    - odprta vprašanja;
    - predlagan commit message.

Po Fazi 1 se ustavi. Ne nadaljuj v modele v2, arbitražo ali QLoRA.
