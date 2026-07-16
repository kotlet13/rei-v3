# REI-v3 — raziskovalni reset in vrnitev k semantičnemu cilju

**Namen:** neposredno izvedbeno navodilo za Codex
**Repozitorij:** `kotlet13/rei-v3`
**Pričakovani trenutni `main`:** `5c53cad56f47e9d1f672038cd6bc2741e449de88`
**Datum:** 2026-07-16
**Status:** ta dokument postane nova aktivna razvojna usmeritev
**Nadomešča za prihodnje delo:** pravilo »vse neposredno na main« in avtomatsko nadaljevanje faz C3–C9 iz prejšnjega načrta

---

# 0. Neposredno navodilo Codexu

Ta dokument je izrecno uporabnikovo navodilo in **nadomešča trenutno pravilo v `AGENTS.md`, ki zahteva neposredno delo na `main`**.

Od tega trenutka naprej:

1. ne delaj neposredno na `main`;
2. ne pushaj neposredno na `main`;
3. ne spreminjaj pravil upravljanja projekta brez izrecnega uporabnikovega navodila;
4. vsaka raziskovalna hipoteza dobi svojo vejo;
5. po vsakem človeško pregledljivem eksperimentu se ustavi;
6. neuspeh eksperimenta ni razlog za gradnjo novega splošnega ogrodja;
7. najprej pridobi signal, šele nato utrjuj infrastrukturo;
8. model-free infrastruktura sama po sebi ni semantični napredek;
9. ne nadaljuj v naslednjo fazo samo zato, ker so testi zeleni;
10. cilj ni izdelati najbolj forenzično zaprt sistem, temveč ugotoviti, kateri računski mehanizmi dejansko koristno predstavljajo Racia, Emocia, Instinkta in Ego.

V prvi odobreni izvedbi smeš narediti samo:

```text
R0 — raziskovalni reset in vrnitev nadzora
X1 — štirislikovni Emocio exploratory screen
```

Po X1 se obvezno ustavi, ne glede na rezultat.

---

# 1. Zakaj je potreben reset

Nova nativna arhitektura je tehnično dobra:

```text
Racio native
Emocio native
Instinkt native
        ↓
immutable NativeMindBundle
        ↓
ordinalni karakter
        ↓
GovernanceMandate
        ↓
Racijeva interpretacija
        ↓
ConsciousDecision
        ↓
BehaviorResultant
        ↓
EgoMeasure / EgoTrace / EgoCompositionSnapshot
```

Temeljne ločitve naj ostanejo.

Težava je razvojni proces po B14:

- C3 je zgradil varen RacioInterpreter, vendar noben model ni prestal kakovostnega gatea;
- C4 je zgradil zelo robusten vizualni runtime, vendar prvi model ni izdelal dovolj uporabnih prizorov;
- C5 je dokazal konsistentnost transparentnega rules enginea, ne še samostojnega Instinktovega razumevanja dogodka;
- C6 je dokazal event-sourcing, projekcije in structured-tag motive, ne še prepoznavanja globoke skladbe iz različno izraženih dogodkov;
- C7 pravilno poroča, da je tehnični contract uspešen, raziskovalna kakovost pa blokirana;
- kljub temu se je razvoj nadaljeval v vedno strožje protokole, manifeste, receipte, runtime inventarje in acceptance dokumente.

Nastala je napačna prioriteta:

```text
validation hardening
pred
exploratory evidence
```

Pravilni vrstni red mora biti:

```text
1. majhen eksperiment
2. človeški pregled rezultata
3. odločitev, ali je smer obetavna
4. šele nato strožja validacija
```

---

# 2. Kanonični cilj projekta

Projekt ne sme optimizirati za lastno testno infrastrukturo.

Njegov dejanski cilj je izdelati simulator, v katerem je mogoče opazovati:

## 2.1 Racio

- jezikovno, številčno, vzročno in časovno procesiranje;
- ločevanje dejstev, domnev in neznank;
- zavestno interpretiranje manifestacij nezavednih razumov;
- možnost pravilne interpretacije, delne interpretacije, racionalizacije ali zmote;
- zavestno odločitev in zavestno pripoved.

## 2.2 Emocio

- notranje prizore;
- trenutno sliko;
- želeno sliko;
- porušeno sliko;
- vizualne oziroma motorične transformacije;
- primerjavo možnih prihodnjih prizorov;
- nativni sklep, ki nastane pred Racijevim opisom.

## 2.3 Instinkt

- trenutno telesno stanje;
- občutek nevarnosti;
- možnost izgube;
- navezanost;
- zaupanje;
- meje;
- pomanjkanje;
- možnost umika;
- asociativni spomin;
- zaščitni nativni sklep pred besedno razlago.

## 2.4 Karakter

- stabilno ordinalno razmerje moči;
- ne trenutna glasnost;
- ne confidence;
- ne stres;
- ne uteženo glasovanje;
- ne sprememba vedenja.

## 2.5 Ego

- ni četrti agent;
- ni vote;
- ni preferred option;
- ni povzetek enega cikla;
- je časovna skladba skupnega delovanja treh razumov;
- v njej se pojavljajo ponavljajoči se motivi, napetosti, prevajalske napake, razrešitve in spoznanja.

---

# 3. Nespremenljivi arhitekturni invarianti

Naslednjih pravil ne spreminjaj.

## 3.1 Nativna neodvisnost

- Profil ne sme vstopiti v nativni procesor.
- R, E in I zaključijo pred governance.
- Native bundle je immutable.
- Poznejša interpretacija ne sme mutirati nativnega sklepa.
- Isti frozen bundle je mogoče uporabiti pri vseh 13 karakterjih.

## 3.2 Zavest

- Racio je edini neposredno zavestni razum.
- `ConsciousDecision.made_by == "R"`.
- To ne pomeni, da je bil izvor sklepa Racio.
- `RacioNative`, `RacioInterpreter` in `RacioNarrator` ostanejo ločeni.

## 3.3 Emocio

- Emocio razmišlja s prizori in slikami.
- Renderirana slika je notranji artefakt, ne zunanje dejstvo.
- Grounded scene, imagined scene in rendered image niso isti objekt.
- Racijev caption ne sme določiti Emocievega nativnega sklepa.
- Vizualni vpliv je dovoljen samo skozi eksplicitno Emocievo vrednotenje.

## 3.4 Instinkt

- Instinktov nativni izhod ni tekstovni monolog.
- Telesni učinek mora imeti izvor, negotovost in možnost abstentiona.
- Body state ne spremeni karakterja.
- Instinktov simulator ni medicinski model.

## 3.5 Governance

- Karakter je ordinalen.
- Parni konflikt nima podrejenega tie-breakerja.
- `R=E=I` uporablja 2-of-3.
- Vsi trije enaki pomenijo `simulated_spoznanje`.
- Governance mandate, conscious decision in behavior resultant ostanejo ločeni.

## 3.6 Ego

- Ego ne odloča.
- Trace je append-only.
- Snapshot je izpeljan.
- Reflektor je lahko samo read-only analitik.
- Racijeva samopodoba se lahko razlikuje od kompozicije.

---

# 4. Nova razvojna disciplina

## 4.1 Veja in pregled

Vse novo delo poteka na feature veji.

Za prvi reset:

```text
codex/research-reset-human-signal
```

Poznejše veje:

```text
codex/emocio-exploration-v2
codex/racio-failure-audit
codex/racio-epistemic-interpreter
codex/instinkt-unseen-scenes
codex/ego-untagged-story
codex/rei-three-demo-integration
```

Noben merge v `main` brez uporabnikovega pregleda.

## 4.2 Codex ne sme sam spreminjati governance

V `AGENTS.md` dodaj izrecno pravilo:

```text
Project-governance instructions may be changed only by explicit user request.
An agent may not remove review gates, require direct-main development, or
authorize itself to continue into another phase.
```

## 4.3 Loči exploration in validation

### Exploration

Namen:

```text
ugotoviti, ali ideja sploh daje uporaben signal
```

Minimalne zahteve:

- model ID;
- revision ali digest, če je dosegljiv;
- seed;
- prompt;
- vhodni artefakt;
- izhodni artefakt;
- trajanje;
- opozorila;
- jasna oznaka `exploratory_no_authority`.

Ni potrebno:

- popoln hash vsake datoteke virtualnega okolja;
- prepoved hardlinkov;
- forenzični runtime inventory;
- atomic member publication;
- immutable display receipt;
- 48-celična matrika;
- production authority;
- popoln cold replay.

### Validation

Namen:

```text
strogo preveriti pristop, za katerega je exploration že pokazal,
da je vsebinsko obetaven
```

Tu se lahko uporabijo:

- exact snapshot manifesti;
- izolirani procesi;
- hard timeout;
- več seedov;
- blinded review;
- cross-language primerjava;
- obstoječa provenance infrastruktura.

Validation ne sme prehiteti explorationa.

## 4.4 Omejitev obsega exploratory faze

Brez dodatne uporabnikove odobritve ena exploratory faza ne sme preseči:

```text
5 novih ali funkcionalno spremenjenih source datotek
3 novih ali funkcionalno spremenjenih testnih datotek
1 poročila
1 uporabniško pregledljivega rezultata
600 neto novih source LOC
300 neto novih test LOC
```

Če to ni dovolj:

- ne prekorači meje;
- poročaj, zakaj;
- predlagaj najmanjši naslednji korak;
- počakaj.

Izjema je samo majhna generated output datoteka izven Gita.

## 4.5 Dokumentacijska disciplina

Za reset uporabljaj en tekoči dnevnik:

```text
Docs/evals/research_reset_2026-07/research_log.md
```

Ne ustvarjaj novih acceptance/addendum/remediation dokumentov za vsak mikro-korak.

Vsak vnos ima:

```text
datum
commit
hipoteza
izveden eksperiment
vidni rezultat
človeška odločitev
naslednji dovoljeni korak
```

## 4.6 Testna disciplina

Exploration:

- focused testi za spremenjeno kodo;
- import/compile check;
- en smoke run.

Pred PR-jem:

- `tests/rei`;
- relevantni `tests/evaluation`;
- nato full suite enkrat.

Ne izvajaj 1000+ testov po vsaki dokumentacijski spremembi.

## 4.7 Kaj šteje kot napredek

Faza šteje kot vsebinski napredek samo, če proizvede vsaj enega od teh rezultatov:

- slike, ki jih lahko človek pregleda;
- konkretno Racijevo interpretacijo in primerjavo z vidnim signalom;
- Instinktov rezultat na prej nevidenem dogodku;
- Ego motiv na zgodbi brez vnaprej ponovljenega taga;
- end-to-end odločitev, pri kateri je mogoče pregledati notranje poti.

Število testov, hashov in novih pogodb samo po sebi ni vsebinski rezultat.

---

# 5. Faza R0 — raziskovalni reset in vrnitev nadzora

**Dovoljena v prvem zagonu.**

## 5.1 Preflight

```powershell
git fetch origin --prune --tags
git switch main
git pull --ff-only origin main
git status --short
git rev-parse HEAD
git log --oneline -12
```

Pričakovani HEAD ob pripravi načrta:

```text
5c53cad56f47e9d1f672038cd6bc2741e449de88
```

Če je drugačen:

- ne resetiraj;
- zapiši dejanski SHA;
- preglej nove commite;
- nadaljuj samo, če ne spreminjajo namena tega načrta.

Dirty tree:

- ne posegaj v uporabnikove spremembe;
- ne stageaj nepovezanih datotek;
- če ovira delo, poročaj in se ustavi.

## 5.2 Zamrzni zgodovinsko točko

Na dejanskem trenutnem `main` ustvari anotiran tag:

```text
rei-v3-pre-research-reset-2026-07-16
```

Ukazi:

```powershell
git tag -a rei-v3-pre-research-reset-2026-07-16 `
  (git rev-parse HEAD) `
  -m "Audit-heavy REI research snapshot before human-signal reset"

git push origin rei-v3-pre-research-reset-2026-07-16
```

Ne premikaj obstoječih tagov.

## 5.3 Ustvari vejo

```powershell
git switch -c codex/research-reset-human-signal
git push -u origin codex/research-reset-human-signal
```

## 5.4 Popravi `AGENTS.md`

Odstrani oziroma nadomesti `Main-Only Development`.

Nova vsebina mora določati:

```text
- feature branches are mandatory;
- direct pushes to main are forbidden;
- user review is required between research phases;
- governance rules cannot be changed by the agent;
- exploration precedes validation;
- model-free infrastructure is not semantic acceptance;
- no phase auto-continues;
- user-owned changes remain unstaged;
- no QLoRA/LoRA/training without a new explicit plan.
```

## 5.5 Označi stari plan kot zgodovinski

Na vrh:

```text
plans/REI_next_phases_merge_semantic_architecture_2026-07-14.md
```

dodaj:

```text
SUPERSEDED FOR FUTURE WORK

M0–C8 remain historical records. The direct-main workflow and automatic
continuation are no longer active. Future work follows:
plans/REI_research_reset_human_signal_2026-07-16.md
```

Ne prepisuj zgodovinskih rezultatov.

## 5.6 Dodaj ta plan v repo

Pot:

```text
plans/REI_research_reset_human_signal_2026-07-16.md
```

## 5.7 Pošteno posodobi `CURRENT.md`

Na vrhu naj bo trenutno stanje:

```text
Architecture status: stable
Technical contract status: strong
Research quality status: blocked
Default model-backed RacioInterpreter: none
Visual native-influence authority: none
Instinkt status: transparent effect-rules engine; raw scene understanding open
Ego status: append-only composition; untagged semantic motif detection open
Active next step: four-image Emocio exploration
```

Izrecno navedi:

- C3 ni sprejet kot modelna kakovost;
- Qwen3.6 official pair je dosegel 23/32 na holdoutu in 23/32 na regressionu, brez phase pass;
- C4 tehnični runtime je sprejet, vizualna semantična kakovost pa ne;
- C5 in C6 sta bounded software contracts;
- C7 research quality ostaja blokirana;
- C9 ni odprt.

## 5.8 Ustvari raziskovalni dnevnik

```text
Docs/evals/research_reset_2026-07/research_log.md
```

Prvi vnos:

```text
R0 — governance reset
```

## 5.9 Testi

Ker R0 ne spreminja runtime kode:

```powershell
python -m pytest `
  tests/test_native_cutover.py `
  tests/test_archive_boundary.py `
  -q
```

Nato:

```powershell
git diff --check
```

## 5.10 Commit

```text
chore(research): restore feature-branch gates and human-signal workflow
```

Po commitu ne mergaj v `main`.

Če R0 uspe, smeš v isti odobreni seji nadaljevati samo v X1.

---

# 6. Faza X1 — štirislikovni Emocio exploratory screen

**Dovoljena v prvem zagonu.**

## 6.1 Raziskovalno vprašanje

Ne preverjamo še produkcijske robustnosti.

Preverjamo samo:

> Ali kateri od že izbranih image-edit modelov lahko iz istega trenutnega prizora izdela dve dovolj ohranjeni, vendar pomensko različni Emocievi prihodnji sliki?

## 6.2 Modela

Uporabi samo že izbrana kandidata:

```text
LongCat-Image-Edit-Turbo
OmniGen-v1-diffusers
```

Ne raziskuj novih modelov.

Ne piši novega model-selection dokumenta.

## 6.3 Vhod

Uporabi isti zamrznjeni C4 Stage 1 source:

```text
source artifact:
image_d1e97e56432b23038b8a01f6fdc24d42

source PNG SHA-256:
72c9fec75d838f0db9a9abc71cbd86c4f4e637c8f54f05c0ea629e12e0f6da58

dimensions:
1024 × 768

options:
enter_circle
remain_edge
```

Uporabi že pripravljene option prompe in seede, če jih obstoječa koda lahko prebere brez novega frameworka.

## 6.4 Točno štirje modelni klici

Vrstni red:

```text
1. LongCat — enter_circle
2. LongCat — remain_edge
3. OmniGen — enter_circle
4. OmniGen — remain_edge
```

Ni dovoljeno:

- best-of-N;
- retry zaradi slabe slike;
- sprememba prompta po prvem rezultatu;
- fallback na drug model;
- dodatni seed;
- dodatni slog;
- drugačen source;
- DINO kot acceptance judge;
- avtomatsko nadaljevanje v 48-cell screen.

Če tehničen klic odpove:

- zapiši napako;
- ne gradi nove splošne varnostne infrastrukture;
- ne poskušaj novega modela;
- zaključi preostale klice samo, če je napaka lokalna za en model in ne ogroža procesa;
- poročaj.

## 6.5 Exploration runtime

Ta faza sme uporabiti obstoječe lokalno, uporabnikovo zaupanja vredno okolje.

Ni potrebno:

- copy-only virtualno okolje;
- preverjanje hardlinkov;
- full Python runtime inventory;
- Windows reparse-point gate;
- enkratna procesna capability;
- atomic member receipt;
- immutable display receipt.

Minimalno obvezno:

```text
repo commit SHA
model ID
model revision/digest, če je znan
runtime version
seed
prompt hash
source PNG hash
output PNG hash
duration
peak VRAM, če ga je enostavno dobiti
warning/error
exploratory_no_authority=true
generated_images_are_external_evidence=false
```

Ne uporabljaj te izjeme za prihodnji validation run.

## 6.6 Implementacija

Najprej poskusi ponovno uporabiti obstoječe adapterje:

```text
app/backend/rei/emocio/longcat_turbo_editor.py
app/backend/rei/emocio/omnigen_editor.py
```

Dovoljena je ena majhna eksploracijska skripta:

```text
scripts/run_rei_emocio_four_image_exploration.py
```

Skripta naj:

- ne spreminja active runtimea;
- ne podeljuje authority;
- ne piše v `knowledge/`;
- ne spreminja C4 approval registryja;
- ne uporablja produkcijskega `visual_cognition` vpliva;
- piše samo v `output/exploration/`.

Če obstoječa adapterja zahtevata preveč validation infrastrukture, napiši tanek wrapper okoli njunega dejanskega model calla. Ne kopiraj 1000 vrstic pogodbenega sistema.

## 6.7 Output

```text
output/exploration/emocio_four_image_screen/{run_id}/
├── manifest.json
├── source.png
├── longcat_enter_circle.png
├── longcat_remain_edge.png
├── omnigen_enter_circle.png
├── omnigen_remain_edge.png
├── contact_sheet.png
└── review_template.md
```

PNG-jev ne commitaj v Git.

V `research_log.md` zapiši:

- run ID;
- absolutna lokalna output pot;
- hash manifesta;
- status štirih klicev;
- čas;
- jasno opozorilo, da rezultat nima semantične avtoritete.

## 6.8 Contact sheet

Razpored:

```text
source | LongCat enter | LongCat remain
source | OmniGen enter | OmniGen remain
```

Na sliko ne dodajaj providerjevih imen čez sam motiv, če bi to motilo pregled. Imena naj bodo v robu oziroma captionu.

## 6.9 Človeški review template

Za vsak output:

```text
source_subject_present: yes / partial / no
identity_preserved: 0 / 1 / 2
composition_preserved: 0 / 1 / 2
option_action_correct: 0 / 1 / 2
extra_actor_or_object: yes / no
internally_useful_as_emocio_scene: yes / uncertain / no
notes:
```

Za vsak modelni par:

```text
two_options_visibly_distinct: yes / uncertain / no
same_underlying_scene: yes / uncertain / no
promising_for_next_experiment: yes / no
```

Codex ne izpolni semantičnega reviewa v imenu uporabnika.

## 6.10 Focused testi

Samo:

- exploration script ne spreminja authority;
- kliče največ štirikrat;
- output je pod `output/exploration`;
- manifest je označen `exploratory_no_authority`;
- ne piše v `knowledge/`;
- ne mutira source;
- ne commitne model weights.

Največ ena nova testna datoteka.

## 6.11 Commit

Commit vsebuje samo:

- tanko exploration skripto;
- focused test;
- posodobljen `research_log.md`.

```text
feat(explore): run bounded four-image Emocio signal screen
```

Output PNG-ji ostanejo lokalni in niso v commitu.

## 6.12 Obvezni stop

Po štirih klicih:

- ne zaženi DINO, če to zahteva novo delo;
- ne spremeni prompta;
- ne zaženi drugega seeda;
- ne odpri Stage 2;
- ne odpri C9;
- ne izdelaj novega acceptance protokola;
- ne mergaj;
- pushaj samo feature vejo;
- poročaj uporabniku;
- počakaj na človeški pregled slik.

---

# 7. Odločitveno drevo po X1

Te faze v prvem zagonu niso dovoljene.

## 7.1 Če je vsaj en model obetaven

Naslednji odobreni eksperiment:

```text
isti model
isti source
isti dve možnosti
3 seedi
= 6 slik
```

Brez:

- drugega sloga;
- drugega jezika;
- drugega modela;
- 48-cell matrike.

Exploratory prag:

```text
vsaj 2/3 uporabne slike za vsako možnost
jasno ločljiva akcija
subjekt prepoznaven
ni bistvene kompozicijske zamenjave
```

To ni produkcijski gate, temveč odločitev, ali se raziskava nadaljuje.

## 7.2 Če noben model ni obetaven

Ne dodajaj tretjega modela avtomatsko.

Najprej izberi enega od treh konceptualnih zaključkov:

```text
A. image editing ni primeren nosilec Emocieve notranje transformacije;
B. current-first source je napačna vizualna osnova;
C. Emocio naj uporablja storyboard/latent/scene-graph, PNG pa samo manifestacijo.
```

Pripravi kratko analizo in počakaj.

## 7.3 Če sta sliki lepi, vendar akciji nista različni

Problem je:

```text
action-conditioned visual rollout
```

Ne:

```text
provenance
runtime inventory
storage
```

Naslednji eksperiment naj spreminja samo prompt/conditioning mehanizem.

---

# 8. Faza X2 — ročni pregled C3 neuspehov

**Ni dovoljena v prvem zagonu.**

## 8.1 Namen

Pred novim modelom ali promptom je treba ugotoviti, ali je trenutni C3 benchmark konceptualno prav zastavljen.

Trenutni gate zahteva exact hidden-motive match. Toda v REI:

- Racio ne vidi skritega nativnega motiva;
- Racio lahko motiv napačno interpretira;
- več hipotez je lahko upravičenih;
- pri dvoumnem signalu je pravilna negotovost pomembnejša od top-1 zadetka.

Zato exact motive accuracy ne sme ostati edina ali glavna metrika.

## 8.2 Vhod

Uporabi:

```text
qwen3.6:35b official holdout
qwen3.6:35b frozen regression
```

Oba sta dosegla 23/32 in nista prestala gatea.

Ne kliči modela.

## 8.3 Preglej vse neuspele primere

Za vsak primer:

```text
case_id
language
source mind
visible observations
gold option
gold action
gold motive
model option
model action
model motive
model confidence
alternative hypotheses
```

Nato klasifikacija:

```text
A — očitna modelna napaka
B — signal ne vsebuje dovolj informacij za gold motiv
C — gold motiv je preozek
D — motivne kategorije se prekrivajo
E — pravilna bi bila top-k hipoteza
F — pravilen bi bil abstention
G — schema/adapter problem
H — bilingual formulation problem
```

## 8.4 Kritično vprašanje

Za vsak gold motiv odgovori:

> Ali bi Racio lahko ta motiv upravičeno sklepal samo iz manifestacije, ki jo je dobil?

Če ne:

- primer ni primeren za exact-motive gate;
- ne popravljaj prompta;
- popravi evaluator ali status primera.

## 8.5 Novi predlagani metrični sloji

### Epistemic validity

- cite visible evidence;
- no unsupported certainty;
- keep alternatives;
- calibrated uncertainty.

### Option/action inference

- ali je Racio razumel smer manifestacije.

### Motive hypothesis coverage

- ali je source-grounded motiv med top-k hipotezami;
- ne zahteva vedno top-1 zadetka.

### Distortion modeling

V conflicted acceptance stanju je lahko racionalizacija:

```text
pričakovan modelirani pojav
```

in ne samo evaluator failure.

### Bilingual consistency

Primerjaj:

- enake hipoteze;
- enako negotovost;
- enako smer;
- ne dobesedno enak wording.

## 8.6 Output

```text
Docs/evals/research_reset_2026-07/c3_failure_audit.md
```

Največ eno poročilo.

Po poročilu se ustavi.

---

# 9. Faza X3 — Racio epistemic interpreter experiment

**Šele po uporabnikovem pregledu X2.**

## 9.1 Ne izbiraj novega modela takoj

Najprej ponovno uporabi `qwen3.6:35b`.

Razlog:

- strukturirani output že deluje;
- ambiguity behavior je močan;
- največji problem je interpretacija motiva in evaluator;
- nov model bi pomešal modelno in metrično spremembo.

## 9.2 Novi izhod

```python
class RacioMotiveHypothesis(BaseModel):
    motive_class: str
    cited_observation_ids: list[str]
    confidence: float
    explanation_short: str

class RacioInterpretation(BaseModel):
    inferred_option_id: str | None
    inferred_action_tendency: str
    motive_hypotheses: list[RacioMotiveHypothesis]
    unresolved_ambiguity: str
    overall_confidence: float
```

Največ tri hipoteze.

Brez chain-of-thoughta.

## 9.3 Exploration corpus

Uporabi 8–12 že znanih primerov samo za razvojno diagnozo.

Ne poročaj generalization claima.

Šele ko je output smiseln:

- precommit nov untouched holdout;
- uporabi obstoječo strogo validacijo.

## 9.4 Človeški pregled

Vprašanja:

- Ali so hipoteze razumne glede na vidni signal?
- Ali model prehitro trdi en sam motiv?
- Ali pravilno ohranja neznanko?
- Ali je gold motiv med razumnimi možnostmi?
- Ali se pokaže smiseln komunikacijski šum?

---

# 10. Faza X4 — Instinkt na nevidenih, netipiziranih dogodkih

## 10.1 Trenutno pošteno ime

Sedanji C5 rezultat obravnavaj kot:

```text
Instinkt effect-rules engine
```

Ne kot dokaz popolne Instinktove native intelligence.

## 10.2 Raziskovalno vprašanje

> Ali sistem iz običajnega opisa dogodka brez vnaprej podanih cue classov prepozna, kaj je za Instinkt pomembno?

## 10.3 Corpus

10 novih scenarijev.

Prepovedano je uporabljati očitne besede:

```text
nevarnost
strah
izguba
umik
meja
pomanjkanje
zaupanje
navezanost
```

Primeri morajo opisati dogodek, ne razlage.

## 10.4 Dve stopnji

### Scene-to-embodiment parser

Izdela samo candidate cues:

```text
possible attachment disruption
possible loss of control
possible escape restriction
possible resource gain
possible trust conflict
```

### Existing rules engine

Šele nato izdela body deltas.

Parser:

- ne vidi karakterja;
- ne izbira končne možnosti;
- ne zapisuje medicinskih diagnoz;
- citira grounded evidence;
- sme abstinirati.

## 10.5 Baseline

Najprej poženi sedanji sistem brez ročnih cue bindingov.

To je pomemben rezultat tudi, če večinoma abstinira.

Ne prikrivaj abstentiona z avtomatsko ročno anotacijo.

## 10.6 Človeški pregled

Za vsak primer:

- kateri cue-i so smiselni;
- kateri manjkajo;
- kateri so izmišljeni;
- ali body deltas sledijo cue-em;
- ali je zaščitna odločitev smiselna;
- ali bi drugačen Instinktov svet spremenil rezultat.

---

# 11. Faza X5 — Ego na eni zgodbi brez ponovljenih tagov

## 11.1 Raziskovalno vprašanje

> Ali Ego prepozna isti motiv, ko se ta skozi življenje pojavlja v različnih dogodkih in besedah?

## 11.2 Corpus

Ena ročno pregledana zgodba:

```text
15 dogodkov
2 resnična ponavljajoča se motiva
5 nepovezanih distractorjev
2 lažni površinski podobnosti
3 Racijeve racionalizacije
3 Instinktovi ponavljajoči se telesni odzivi
3 Emocieve različne slike iste globlje želje
```

V dogodkih ne ponavljaj istega canonical taga.

## 11.3 Baseline

Najprej poženi obstoječi structured-tag motif engine brez prilagoditve.

Pričakovan neuspeh je uporaben rezultat.

## 11.4 Ozka semantična hipoteza

Če baseline ne prepozna motiva:

- embedding clustering lahko samo predlaga motif;
- vsak predlog mora citirati measure IDs;
- človek ga potrdi ali zavrne;
- ne zapisuje v MindWorld;
- ne vpliva na governance;
- ne postane Ego agent.

## 11.5 Uspeh

Ni potreben 1.0 score.

Prvi uporaben cilj:

- oba resnična motiva sta med predlogi;
- največ en lažni motiv;
- vsi predlogi imajo pravilne evidence;
- Racijeva samopodoba se lahko primerja s kompozicijo.

---

# 12. Faza X6 — tri end-to-end demonstracije

Šele ko X1–X5 dajo vsaj en uporaben rezultat.

## 12.1 Demo A — Emocio

- trenutna slika;
- želena slika;
- dve prihodnji sliki;
- Emociev sklep;
- Racijeva interpretacija;
- karakter `E>R>I`;
- conscious decision;
- EgoMeasure.

## 12.2 Demo B — Instinkt

- običajen dogodek brez cue oznak;
- scene-to-embodiment;
- body rollout;
- Instinktov sklep;
- karakter `I>R>E`;
- conscious decision;
- vedenje.

## 12.3 Demo C — komunikacijski šum

- Emocio ali Instinkt izbere smer;
- Racio pravilno razume option, napačno pa motiv;
- karakter podeli mandat;
- conscious narrative racionalizira;
- Ego zapiše TranslationGap.

Za vsak demo največ tri karakterje, ne vseh 13.

Output:

```text
Docs/evals/research_reset_2026-07/three_demo_report.html
```

Človek mora lahko vse pregledati na eni strani.

---

# 13. Kdaj se validation ponovno vključi

Obstoječa auditna infrastruktura se ne briše.

Ponovno se uporabi samo po pozitivnem exploratory signalu.

## 13.1 Vizualni staged gate

### V0

```text
2 modela × 2 možnosti = 4 slike
```

Človeški signal.

### V1

```text
1 obetaven model × 2 možnosti × 3 seedi = 6 slik
```

Preveri osnovno stabilnost.

### V2

```text
1 model × 2 možnosti × 3 seedi × 2 jezika = 12 slik
```

Šele tukaj bilingual.

### V3

Slog in option-order perturbacije samo, če V2 ostane obetaven.

Ni avtomatskega 48/48 all-or-nothing gatea.

## 13.2 Racio staged gate

### R0

Znani primeri za metrično diagnozo.

### R1

Nov untouched holdout.

### R2

Structured proti VLM ablation.

### R3

Longitudinal communication noise.

## 13.3 Instinkt staged gate

### I0

10 unseen raw scenes.

### I1

20 source-grounded scenes.

### I2

world/body counterfactuals.

### I3

outcome learning.

## 13.4 Ego staged gate

### E0

ena 15-event zgodba.

### E1

tri zgodbe.

### E2

blind human motif review.

### E3

longitudinal system integration.

---

# 14. Česa Codex ne sme narediti

1. Ne delaj neposredno na `main`.
2. Ne spreminjaj governance pravil brez izrecnega navodila.
3. Ne nadaljuj po X1.
4. Ne ustvarjaj nove feature veje znotraj prve veje.
5. Ne premikaj baseline tagov.
6. Ne briši obstoječe auditne infrastrukture.
7. Ne gradi copy-only venv v prvem zagonu.
8. Ne rešuj hardlinkov ali reparse pointov.
9. Ne dodajaj novega generičnega receipt sistema.
10. Ne ustvarjaj še enega remediation protokola.
11. Ne odpiraj 48-cell visual matrix.
12. Ne izbiraj novega image modela.
13. Ne izbiraj novega Racio modela.
14. Ne prompt-tunaj na istem holdoutu.
15. Ne spreminjaj golda, da model zmaga.
16. Ne uporabljaj DINO kot nadomestilo za človeški pregled.
17. Ne izpolnjuj človeškega reviewa sam.
18. Ne podeljuj semantic ali production authority.
19. Ne spreminjaj visual authority registryja.
20. Ne omogoči generated images kot external evidence.
21. Ne generiraj training datasetov.
22. Ne uvajaj LoRA, QLoRA ali SFT.
23. Ne naredi Ega za agenta.
24. Ne spremeni karakterja v uteži.
25. Ne pošiljaj profila nativnim procesorjem.
26. Ne uporabljaj LLM-ja kot governance tie-breakerja.
27. Ne razglašaj rules-engine passa za dokaz Instinktove inteligence.
28. Ne razglašaj structured-tag passa za dokaz Ego semantičnega razumevanja.
29. Ne označi tehničnega passa za research-quality pass.
30. Ne ustvarjaj releasea C9.

---

# 15. Poročilo po prvem zagonu

Po R0 + X1 odgovori v tem formatu:

```text
Phase: R0 + X1
Branch:
Base main SHA:
Reset commit SHA:
Exploration commit SHA:
Tag created:
Changed files:
New source LOC:
New test LOC:
Tests run:
Tests passed:
Tests failed:

Models called:
Model call count:
Source image SHA:
Output directory:
Output manifest SHA:
Generated outputs:
Technical failures:
Warnings:

Semantic review performed by Codex: no
Semantic authority granted: no
Production authority granted: no
External-evidence authority granted: no

What a human must inspect:
1.
2.
3.

Blocked items:
Next possible branches:
- promising visual pair
- failed visual concept
- technical environment blocker

PR opened: no
Merged to main: no
```

---

# 16. Definition of success za raziskovalni reset

Reset je uspešen, ko velja:

- `main-only` pravilo je odpravljeno;
- uporabnik ima ponovno review gate;
- trenutni audit-heavy snapshot je označen s tagom;
- `CURRENT.md` pošteno kaže research blockers;
- Codex ni sam nadaljeval v naslednjo fazo;
- ustvarjene so največ štiri slike;
- slike so človeško pregledljive;
- rezultat ne nosi semantične ali produkcijske avtoritete;
- ni nastal nov splošni security framework;
- naslednji korak je odvisen od človeškega pregleda, ne od zelenih testov.

---

# 17. Dolgoročni cilj

Projekt je spet na pravi poti, ko lahko na majhnem številu preglednih primerov pokaže:

```text
Emocio je iz dogodka ustvaril notranje prizore, ki so res vplivali na njegov sklep.

Instinkt je iz običajnega dogodka prepoznal zaščitno pomembne elemente,
jih preslikal v telo in prišel do svojega sklepa.

Racio je videl samo njune manifestacije, jih interpretiral,
nekaj razumel in nekaj popačil.

Karakter je določil, kateri sklep ima oblast,
ne da bi spremenil vsebino nativnih procesorjev.

Zavestna odločitev in vedenje sta ostala ločena.

Ego je skozi različne dogodke prepoznal skladbo,
ne da bi bil motiv vnaprej zapisan z istim tagom.
```

To je cilj. Vsa infrastruktura je samo podpora temu cilju.
