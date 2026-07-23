# Codex kickoff — REI native-composition merge preflight

> **STATUS: HISTORICAL — COMPLETED / DO NOT EXECUTE**
>
> Ta kickoff je bil izveden in je ohranjen samo kot sled opravljenega
> merge-preflight dela. Za novo delo uporabi trenutno stanje projekta in nov,
> izrecno potrjen načrt.

Repozitorij: `kotlet13/rei-v3`

Najprej preberi:

`plans/REI_next_phases_merge_semantic_architecture_2026-07-14.md`

Izvedi samo **Fazo M0 — pre-merge pregled**.

## Prepovedi

- Ne spreminjaj runtime kode.
- Ne mergeaj še ničesar.
- Ne rebasaj.
- Ne force-pushaj.
- Ne premikaj ali briši tagov.
- Ne začenjaj semantic-lab faze.
- Ne dodajaj modelov ali QLoRA.

## Ukazi

```powershell
git fetch origin --prune --tags
git status --short
git branch -avv
git log --graph --decorate --oneline --all -40
git rev-parse origin/main
git rev-parse origin/codex/architecture/rei-native-composition
git merge-base origin/main origin/codex/architecture/rei-native-composition
git diff --stat origin/main...origin/codex/architecture/rei-native-composition
```

Preveri:

- dejanski SHA obeh vej;
- ahead/behind;
- merge base;
- kateri commit manjka arhitekturni veji;
- star canonical-v2/QLoRA prompt;
- B14 acceptance report;
- arhivski tag in rollback;
- ali obstaja odprt PR;
- ali obstaja CI;
- dirty tree;
- potencialne konflikte in podvojene dokumente.

Ustvari samo:

`Docs/evals/merge_preflight_native_composition_2026-07-14.md`

Če je poročilo commitano, uporabi:

`docs(integration): record native-composition merge preflight`

Po tem se ustavi in poročaj po formatu iz glavnega načrta.
