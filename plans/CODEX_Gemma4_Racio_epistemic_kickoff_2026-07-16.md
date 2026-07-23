# Codex kickoff — Gemma 4 31B Racio epistemic development screen

Repozitorij: `kotlet13/rei-v3`

Najprej preberi:

```text
plans/REI_gemma4_racio_epistemic_continuation_2026-07-16.md
```

Izvedi samo:

```text
G0 — zaključek X2 in projektno stanje
G1 — epistemološki output contract v2
G2 — Gemma 4 31B lokalni preflight
G3 — omejen 16-case development screen
```

Po G3 se obvezno ustavi.

## Git

Začni na:

```text
codex/racio-failure-audit
```

Zaženi:

```powershell
git fetch origin --prune --tags
git switch codex/racio-failure-audit
git pull --ff-only origin codex/racio-failure-audit
git status --short
git rev-parse HEAD
git log --oneline -15
```

Nato ustvari:

```text
codex/racio-gemma4-epistemic-interpreter
```

Ne mergeaj v `main`.
Ne odpiraj PR-ja.

## G0

1. V `c3_failure_audit.md` dodaj `Human review decision`.
2. Sprejmi audit brez retroaktivnega passa Qwena.
3. Zapiši popravke:
   - H3 = taxonomy gap `desired_scene_absent`, ne samodejni body/boundary alarm;
   - H7 = `set_boundary` action ne dokazuje `boundary_alarm` motiva;
   - H11 = protective-alarm hierarchy, kjer je boundary lahko podtip širše družine.
4. Zapiši, da je `gemma4:31b` edini novi kandidat.
5. Posodobi `CURRENT.md` z Emocio rezultati in Racio statusom.
6. Popravi nedvoumne placeholder SHA-je v research logu.
7. Commit:
   `docs(racio): accept X2 audit amendments and select Gemma 4 31B`

## G1

1. V1 C3 schema, provider, prompt, hashi in evidence ostanejo nespremenjeni.
2. Dodaj v2, ki loči:
   - action;
   - option;
   - motive hypotheses;
   - ločene confidence;
   - unresolved ambiguity.
3. Največ tri citirane motive hypotheses.
4. Action ne sme avtomatsko določiti motiva.
5. Option description ne sme ustvariti hidden signala.
6. Pri dveh modalnostih iste akcije je pravilen null option.
7. Dodaj 8–12 deterministično izbranih pass zapisov v simetrični audit.
8. Dodaj focused teste.
9. Commit:
   `feat(racio): add epistemic interpretation contract and evaluator v2`

## G2

Uporabi samo:

```text
gemma4:31b
```

Najprej preveri lokalni model in exact digest.

Če model ni nameščen:
- ne uporabi aliasa;
- ne uporabi clouda;
- ne izberi drugega modela;
- ustavi se in poročaj.

Za začetni profil:

```text
num_ctx=65536
num_gpu=999
require_full_gpu=true
seed=314159
temperature=0.0
top_p=0.95
top_k=64
num_predict=2048
stream=false
fallback=none
retry=none
```

Thinking:
- system prompt začne z `<|think|>`;
- final output mora biti ločen JSON;
- evaluator ne vidi thinking vsebine;
- shrani samo thinking hash/size metadata, ne celotnega tracea v Git.

Izvedi en tehnični probe.
Preveri `wsl ollama ps` in 100% GPU.

Ne spreminjaj Qwen providerja.

Commit:
`feat(racio): add pinned local Gemma 4 epistemic provider`

## G3

Uporabi 8 roots × sl/en = 16 calls:

- H1
- H3
- H7
- H11
- H15
- R1
- R3
- R5

Pripravi naturalized manifestation variante.
Ne pošiljaj samo `structured_tendency:*` lookup oznak.

Pred runom zamrzni:

- case order;
- case hashes;
- prompt hash;
- schema hash;
- model digest;
- runtime settings;
- exactly 16 calls.

Prepovedano:

- retry;
- fallback;
- prompt change po prvem outputu;
- Qwen call;
- nov model;
- drugi seed;
- temperature ablation;
- image input;
- untouched-holdout claim;
- model promotion.

Poročilo:

```text
Docs/evals/research_reset_2026-07/gemma4_racio_epistemic_dev_screen.md
```

Poročaj ločeno:

- structure;
- action;
- option;
- abstention;
- motive hypotheses;
- unsupported overclaims;
- confidence;
- bilingual consistency.

Ne izdelaj enega REI scorea.

Commit:
`feat(eval): run bounded Gemma 4 Racio epistemic screen`

Po commitu:

- pushaj samo feature vejo;
- ne odpiraj PR-ja;
- ne mergeaj;
- ustavi se;
- poročaj po formatu iz glavnega plana.
