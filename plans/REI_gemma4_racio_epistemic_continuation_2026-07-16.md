# REI-v3 — Gemma 4 31B: nadaljevalni načrt za epistemološko pravilnega RacioInterpreterja

**Namen:** neposredno izvedbeno navodilo za Codex
**Repozitorij:** `kotlet13/rei-v3`
**Trenutna raziskovalna veja:** `codex/racio-failure-audit`
**Znani merge base z `main`:** `5c53cad56f47e9d1f672038cd6bc2741e449de88`
**Operatorjev izbrani naslednji model:** `gemma4:31b`
**Datum načrta:** 2026-07-16
**Status:** nova aktivna smer za nadaljevanje C3/X3 raziskave
**Nadomešča:** nadaljnje modelno delo s `qwen3.6:35b`; Qwenovi uradni rezultati ostanejo zamrznjeni zgodovinski baseline

---

# 0. Neposredno navodilo Codexu

Uporabnik je sprejel odločitev, da se naslednja raziskovalna iteracija RacioInterpreterja izvede z:

```text
gemma4:31b
```

To ni dovoljenje za:

- modelni turnir;
- nov krog izbire modelov;
- nadaljnje prompt-tunanje Qwena;
- fallback iz Gemme na Qwen;
- spreminjanje zamrznjenih Qwen rezultatov;
- retroaktivno popravljanje starega 23/32 rezultata;
- avtomatsko napredovanje do produkcijske avtoritete;
- uporabo Gemme kot skupnega možgana Racia, Emocia in Instinkta.

Gemma 4 31B postane **edini novi kandidat za model-backed RacioInterpreter** v tem ciklu.

Prvi dovoljeni izvedbeni sklop je:

```text
G0 — zaključek človeškega pregleda X2 in zamrznitev pravilnega problema
G1 — epistemološki izhodni contract v2 in popravek evaluatorjeve logike
G2 — Gemma 4 31B lokalni preflight
G3 — omejen razvojni Gemma screen na znanih, človeško pregledanih primerih
```

Po G3 se Codex obvezno ustavi.

V prvem sklopu ni dovoljeno:

- izdelati novega untouched holdouta in ga že pognati;
- promovirati model;
- integrirati Gemme v aktivni runtime;
- odpreti multimodalni image-to-Racio experiment;
- spremeniti governance ali Ego;
- nadaljevati na Instinkt;
- generirati training dataset;
- uvesti QLoRA, LoRA ali SFT.

---

# 1. Ponovno preverjena kanonična podlaga REI

Ta razdelek je arhitekturna osnova. Codex ga mora prebrati pred spremembo sheme, prompta ali evaluatorja.

Primarni dokumenti v repozitoriju oziroma uporabnikovi dokumentaciji:

```text
Docs/REI osnove.docx
Docs/REI osnova Racio.docx
Docs/REI osnova Emocio.docx
Docs/REI osnova Instinkt.docx
Docs/Eros - pogovori.pdf
```

Če so poti po cutoverju ali arhiviranju drugačne, naj Codex najde dejanske sledene datoteke. Izvornih dokumentov ne spreminjaj.

## 1.1 Trije razumi so neodvisni procesorji

REI ne govori o enem razumu s tremi razpoloženji. Govori o treh neodvisnih sistemih:

```text
Racio
Emocio
Instinkt
```

Vsak:

- procesira isti dogodek po svojem konceptu;
- ima svoj svet;
- uporablja svoj spomin;
- pride do svojega sklepa;
- zase meni, da razmišlja pravilno;
- lahko pride do istega zunanjega dejanja po povsem drugi poti kot druga dva.

Iz tega sledi:

```text
enako vedenje ≠ enaka notranja pot
enak option ID ≠ enak motiv
enaka akcijska težnja ≠ isti razum
```

To mora veljati tudi v evaluatorju.

## 1.2 Karakter je pot in razmerje moči

Karakter:

- ni rezultat razmišljanja;
- ni trenutna intenzivnost;
- ni vedenjska oznaka;
- ni zbirka stereotipov;
- ni confidence score;
- ni dinamična utež.

Karakter določa **razmerje moči med tremi načini procesiranja**.

Nativni procesorji zato še naprej ne smejo dobiti:

```text
character_profile
authority_tier
profile_weight
resultant_leader
```

RacioInterpreter v tej fazi prav tako ne sme dobiti karakterja. Naloga interpreterja je razumeti vidno manifestacijo, ne ugibati hierarhije osebe.

## 1.3 Racio — pravilna osnova

Racio je:

- najmlajši razum;
- edini razum, ki se ga neposredno zavedamo;
- besedni in številčni procesor;
- analitičen;
- sistematičen;
- dosleden;
- natančen;
- načrtovalen;
- sposoben predvidevanja;
- sposoben razmejevanja časa;
- sposoben zavestne razlage in zavestne odločitve.

Toda Racio ni:

- objektivna resnica;
- neposreden bralnik Emocia;
- neposreden bralnik Instinkta;
- nujno pravilen interpreter;
- razsodnik, ki pozna skriti motiv;
- dokaz, da je besedna razlaga enaka izvorni nezavedni poti.

Ključna kanonična posledica:

> Vse, česar se človek zaveda — tudi slike v zavesti, občutki, strahovi in razlage teh občutkov — je že prišlo skozi Racia.

Zato mora simulator razlikovati:

```text
EmocioNativeConclusion
EmocioManifestation
RacioInterpretationOfEmocio
```

in:

```text
InstinktNativeConclusion
InstinktManifestation
RacioInterpretationOfInstinkt
```

Racio lahko:

- pravilno prepozna smer;
- pravilno prepozna dejanje, ne pa motiva;
- vidi več možnih motivov;
- racionalizira;
- zamenja akcijo za vzrok;
- pretirano samozavestno izbere eno razlago;
- pošteno abstinira;
- sploh ne razume signala.

To niso nujno programske napake. Nekatere so legitimni modelirani pojavi.

## 1.4 Emocio — pravilna osnova

Emocio:

- razmišlja s slikami;
- slike sestavlja v mozaike in celote;
- lahko deluje vizualno ali motorično;
- je povezan s prepoznavanjem osebkov in prilagojenosti;
- je zaupljiv in usmerjen v dobro sliko;
- išče nove izkušnje;
- improvizira;
- je tekmovalen;
- želi biti v središču slike;
- njegova obramba je napad.

Za interpreter je posebej pomembna dinamika prizorov:

```text
trenutna slika
prejšnja slika
želena / "naj bi bila" slika
porušena slika
ponavljajoča se porušena slika
```

Želja ni zgolj besedni cilj. Je pritisk, da se želena slika pretvori v trenutno sliko.

Jeza lahko nastane, ko:

```text
želena slika
→ ne more postati trenutna slika
→ se dokončno poruši
```

Racio nato jezo ozavesti in ji pogosto izdela svojo razlago, ki ni nujno pravilna.

Zelo pomembno:

```text
set_boundary kot akcija
ne dokazuje
boundary_alarm kot motiv
```

Emocio lahko postavi mejo zato, ker se njegova slika ponavlja in ruši. Akcija je lahko podobna Instinktovi, notranja pot pa drugačna.

Prav tako:

```text
connect kot akcija
ne dokazuje
attachment kot motiv
```

Emocio se lahko povezuje zaradi slike, vključitve, socialnega mozaika, pozornosti ali motoričnega vzorca, ne zaradi Instinktove navezanosti.

## 1.5 Instinkt — pravilna osnova

Instinkt je:

- najstarejši razum;
- usmerjen v varovanje;
- usmerjen v prepoznavanje nevarnosti;
- previden;
- nezaupljiv;
- sumničav;
- nagnjen k črnemu scenariju;
- povezan s strahom;
- povezan z izgubo;
- povezan z navezanostjo;
- povezan z občutki;
- povezan z zaščitnimi mejami;
- povezan z umikom oziroma begom;
- povezan s pomanjkanjem;
- povezan z vonjem, okusom in telesnimi zaznavami;
- asociativen;
- čas dojema drugače kot Racio.

Instinkt ne operira na ravni besednih argumentov. Njegov jezik so:

```text
občutki
telesna stanja
podobne situacije
izkušnje
bližina
izguba
nevarnost
umik
zaupanje
meja
pomanjkanje
```

Zato mora Racio o Instinktu sklepati posredno.

Zelo pomembno:

```text
protect kot akcija
ne dokazuje nujno
general_body_alarm kot motiv
```

in:

```text
seek_safety
lahko izvira iz:
- splošnega telesnega alarma,
- meje,
- izgube nadzora,
- nevarnosti za navezanost,
- pomanjkanja,
- nezaupanja,
- nedostopnega umika.
```

Instinktove motive je zato treba obravnavati hierarhično in kot hipoteze.

## 1.6 Besede in zavestni dostop

Kanonično pravilo:

```text
besede neposredno posluša Racio
Emocio in Instinkt zaznavata druge kanale
```

To pomeni:

- prompt je vedno Racijev artefakt;
- tekstovni opis Emocieva ali Instinktova sveta ni njun dobesedni notranji jezik;
- tekstovni benchmark je približek Racijevega dostopa do manifestacij;
- interpreter ne sme biti nagrajen za poznavanje skritega native ground trutha;
- option description ni dokaz o tem, kaj je nezavedni razum manifestiral.

## 1.7 Spoznanje

Spoznanje ni Racijeva samozavestna razlaga.

Spoznanje pomeni:

```text
Racio pride do sklepa po svoji poti
Emocio pride do istega sklepa po svoji poti
Instinkt pride do istega sklepa po svoji poti
```

RacioInterpreter zato ne ustvarja spoznanja. Samo zavestno interpretira omejeni signal.

## 1.8 Ego

Ego ostane:

```text
EgoMeasure
EgoTrace
EgoCompositionSnapshot
```

Gemma v tej fazi:

- ne odloča kot Ego;
- ne popravlja EgoTracea;
- ne piše neposredno v svetove;
- ne postane četrti agent;
- ne določa karakterja.

---

# 2. Ključni sklep X2 failure audita

Stari C3 rezultat:

```text
qwen3.6:35b
23/32 holdout
23/32 regression
```

ostane zgodovinsko veljaven.

Ne spremeni se v pass.

Toda failure audit je pravilno pokazal, da en sam exact boolean meša več različnih problemov:

```text
A. jasna modelna napaka
B. signal ne vsebuje dovolj informacij za gold
D. prekrivanje oziroma hierarhija motivnih kategorij
F. option je poddeterminiran in pravilen je abstention
H. slovensko-angleška nestabilnost
```

Poleg tega je model v vseh 18 neuspelih zapisih vrnil:

```text
alternative_hypotheses = []
```

ob visoki samozavesti.

To je pomemben raziskovalni neuspeh. RacioInterpreter ni samo klasifikator. Njegova bistvena kvaliteta je epistemološka:

```text
kaj je res videl
kaj neposredno sledi iz videnega
kaj je le hipoteza
česa ne more vedeti
kdaj mora abstinirati
```

---

# 3. Človeška odločitev glede X2

Codex mora v `c3_failure_audit.md` dodati razdelek:

```text
## Human review decision — 2026-07-16
```

Vsebina:

## 3.1 Sprejeto

Uporabnik sprejema:

- da model ni retroaktivno uspešen;
- da exact top-1 gate ni dovolj kot edina metrika;
- da so jasne action napake še vedno modelne napake;
- da sta R1 in H15 poddeterminirana na ravni optiona;
- da je pri poddeterminiranem signalu pravilen null option in izrecna negotovost;
- da mora naslednji output omogočiti več citiranih motivnih hipotez;
- da je za kakršen koli generalization claim potreben nov untouched holdout;
- da je `gemma4:31b` naslednji in edini novi modelni kandidat.

## 3.2 Popravki audita

### H3 — `desired_scene_absent`

H3 ni dobro opisan samo kot overlap:

```text
broken_scene
vs.
body_alarm
```

Vidna informacija je bližje:

```text
desired_scene_absent
low_attraction_to_planned_exercise
```

Zato:

- `boundary_alarm` ostane nepodprt modelni overclaim;
- `body_alarm` prav tako ni neposredno manifestiran;
- `broken_scene` je preširok oziroma nenatančen gold;
- v2 mora razlikovati:
  - `desired_scene_absent`,
  - `desired_scene_mismatch`,
  - `broken_scene`,
  - `recurrent_broken_scene`;
- če ta ločitev ni mogoča, je motive hypothesis `unknown` bolj pošten od prisilnega starega enuma.

### H7 — akcija ni motiv

Vidno:

```text
recurrent broken scene
action tendency = set_boundary
```

Iz `set_boundary` ne sledi nujno:

```text
motive = boundary_alarm
```

Zato:

- `broken_scene` oziroma `recurrent_broken_scene` ostane bolje podprt motivni vir;
- `boundary_alarm` ni sprejet samo zato, ker je akcija `set_boundary`;
- evaluator mora preprečiti sklepanje motiva neposredno iz imena akcije.

### H11 — hierarhija alarmov

Vidno:

```text
boundary_alarm
seek_safety
```

Stari gold:

```text
body_alarm
```

Model:

```text
boundary_alarm
```

To ni nujno top-k konflikt med dvema popolnoma ločenima kategorijama. Bolj pravilna struktura je:

```text
protective_alarm
├── general_body_alarm
├── boundary_alarm
├── attachment_alarm
├── resource_alarm
├── trust_alarm
└── escape_alarm
```

`boundary_alarm` je lahko natančnejši podtip širše zaščitne družine, če ga vidna manifestacija podpira.

## 3.3 Omejitev failure-only audita

X2 je pregledal neuspehe, ne pa simetričnega vzorca uspehov.

Pred spremembo evaluatorja je obvezen majhen pass audit:

- 8 do 12 starih pass zapisov;
- stratificirano in vnaprej izbrano;
- ne cherry-picked;
- pregled javne površine pred goldom;
- preverjanje, ali so pass rezultati epistemološko dobri ali samo exact-correct.

---

# 4. Modelna odločitev: Gemma 4 31B

## 4.1 Točen model

Uporabi samo:

```text
gemma4:31b
```

Ne uporabljaj:

```text
gemma4:latest
gemma4:cloud
gemma4:31b-cloud
gemma4:26b
Gemma 3
kakršnega koli neuradnega aliasa
```

## 4.2 Zakaj je model primeren za naslednjo fazo

Operator ga je v lastni uporabi večkrat ocenil kot zanesljivejšega.

Poleg tega je model:

- dense 31B razred;
- text + image model;
- dolgokontekstni;
- večjezičen;
- sposoben system role;
- primeren za strukturiran lokalni Ollama runtime;
- potencialno uporaben pozneje kot Racijev VLM nad Emocievimi slikami.

Ta zadnja točka je pomembna:

> Gemma 4 sme pozneje gledati Emocieve slike samo v vlogi Racia, ki jih interpretira. Ne sme postati Emocio.

## 4.3 Qwenov novi status

`qwen3.6:35b` je od zdaj:

```text
frozen historical comparison baseline
```

Prepovedano:

- nadaljnje prompt-tunanje;
- nov model call za popravljanje starega scorea;
- fallback iz Gemme;
- združevanje outputov Qwena in Gemme;
- ensemble;
- majority vote;
- model judge nad drugim modelom.

---

# 5. Git in veja

## 5.1 Preflight

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
git diff --stat origin/main...HEAD
```

Če je delovno drevo dirty:

- ne resetiraj;
- ne stageaj uporabnikovih nepovezanih sprememb;
- poročaj in se ustavi, če spremembe ovirajo delo.

## 5.2 Nova veja

Iz dejanskega head-a `codex/racio-failure-audit` ustvari:

```text
codex/racio-gemma4-epistemic-interpreter
```

```powershell
git switch -c codex/racio-gemma4-epistemic-interpreter
git push -u origin codex/racio-gemma4-epistemic-interpreter
```

Ne mergeaj v `main`.

Ne odpiraj PR-ja v prvem sklopu.

---

# 6. G0 — zaključek X2 in projektno stanje

## 6.1 Spremeni samo dokumentacijo

Posodobi:

```text
Docs/evals/research_reset_2026-07/c3_failure_audit.md
Docs/evals/research_reset_2026-07/research_log.md
CURRENT.md
```

## 6.2 `c3_failure_audit.md`

Dodaj človeško odločitev iz 3. poglavja tega načrta.

Ne spreminjaj:

- zamrznjenih tabel rezultatov;
- 23/32;
- originalnih Qwen outputov;
- hashov;
- starega golda;
- zgodovinske klasifikacije brez jasnega dodatka.

Uporabi izraz:

```text
human amendment
```

ne:

```text
retroactive correction
```

## 6.3 `research_log.md`

Dodaj:

```text
X2 — human review decision and Gemma 4 selection
```

Vključi:

- datum;
- audit branch SHA;
- odločitev za `gemma4:31b`;
- H3/H7/H11 popravke;
- Qwen ostane frozen;
- naslednji korak G1;
- brez modelnega klica v G0.

Popravi placeholderje:

```text
this entry's commit (resolve from Git history)
```

z dejanskimi SHA-ji, kjer jih je mogoče nedvoumno določiti.

## 6.4 `CURRENT.md`

Trenutni vrh naj postane:

```text
Architecture status: stable
Technical contract status: strong
Research quality status: blocked

Emocio exploration:
- LongCat selected as promising;
- ENTER accepted in 2/3 reviewed roots;
- English REMAIN accepted in 3/3 reviewed roots;
- no visual native-influence authority yet.

RacioInterpreter:
- Qwen official pair remains 23/32 + 23/32 and not accepted;
- X2 failure audit human-reviewed with H3/H7/H11 amendments;
- next candidate: gemma4:31b;
- next active phase: epistemic output v2 and bounded Gemma development screen.

Instinkt:
- transparent effect-rules engine;
- raw scene understanding still open.

Ego:
- append-only composition;
- untagged semantic motif detection still open.
```

## 6.5 Commit

```text
docs(racio): accept X2 audit amendments and select Gemma 4 31B
```

---

# 7. G1 — Racio epistemic output contract v2

## 7.1 Namen

Stari output je preveč zlit:

```text
option
action
motive
confidence
```

z enim samim exact goldom.

Novi output mora ločiti:

```text
kaj je Racio videl
kakšno akcijsko težnjo je prepoznal
ali vidni signal določa eno možnost
katere motive lahko samo hipotetično predlaga
koliko je prepričan v vsako ločeno trditev
kaj ostaja neznano
```

## 7.2 V1 ostane zamrznjen

Ne spreminjaj:

```text
StructuredRacioInterpreterOutput
uradnega C3 v1 schema hasha
uradnega Qwen provider instruction hasha
uradnih runnerjev in evidence
```

Dodaj nov v2 vzporedno.

Predlagana lokacija:

```text
app/backend/rei/communication/epistemic_interpreter.py
```

## 7.3 Novi tipi

```python
MotiveFamily = Literal[
    "scene",
    "motor_social",
    "protection",
]

SceneMotiveSubtype = Literal[
    "desired_scene_absent",
    "desired_scene_mismatch",
    "broken_scene",
    "recurrent_broken_scene",
    "scene_realization",
    "scene_repair",
]

MotorSocialMotiveSubtype = Literal[
    "motor_execution",
    "connection",
    "competition",
    "attention_or_status",
]

ProtectionMotiveSubtype = Literal[
    "general_body_alarm",
    "boundary_alarm",
    "attachment_alarm",
    "resource_alarm",
    "trust_alarm",
    "escape_alarm",
]
```

To je **implementation hypothesis**, ne neposredna trditev iz knjige. Vpiši jo tudi v:

```text
knowledge/canon_v2/open_questions.md
```

z razlago, da hierarhija operacionalizira kanonične razlike, vendar še ni empirično potrjena.

## 7.4 `MotiveHypothesis`

```python
class MotiveHypothesis(FrozenModel):
    family: MotiveFamily
    subtype: NonEmptyId
    cited_observation_ids: tuple[NonEmptyId, ...]
    confidence: Score01
    explanation_short_sl: NonEmptyText
```

Validatorji:

- največ 3 hipoteze v outputu;
- hipoteze so urejene po padajoči confidence;
- vsaka citira vsaj eno vidno observation;
- ne citira skritega native trutha;
- `subtype` mora pripadati izbrani family;
- ista family/subtype kombinacija se ne ponovi;
- explanation je kratek;
- brez character oznak;
- brez diagnoz;
- brez trditev, da je motiv dejstvo.

## 7.5 `RacioEpistemicInterpretationV2`

```python
class RacioEpistemicInterpretationV2(FrozenModel):
    source_mind: Literal["E", "I"]
    cited_observation_ids: tuple[NonEmptyId, ...]

    inferred_action_tendency: InterpreterActionTendency
    action_confidence: Score01

    inferred_option_id: NonEmptyId | None
    option_confidence: Score01

    motive_hypotheses: tuple[MotiveHypothesis, ...]
    motive_unknown_reason: NonEmptyText | None

    unresolved_ambiguity: NonEmptyText | None
```

Pravila:

### Action

- akcija je ločena od motiva;
- če je action cue neposredno viden, ga je dovoljeno natančno prepoznati;
- akcija ne določi avtomatsko motive family;
- `set_boundary` ne ustvari `boundary_alarm`;
- `connect` ne ustvari `attachment_alarm`;
- `protect` ne ustvari `general_body_alarm`;
- `seek_safety` ne določi specifičnega podtipa brez dodatnega signala.

### Option

- option se izbere samo, če vidni signal razlikuje javne možnosti;
- option description se uporablja za mapiranje že prepoznane smeri;
- option description se ne sme uporabiti kot dokaz skritega motiva;
- kadar dve možnosti uresničujeta isto akcijo na različna načina in manifestacija ne izbere modalnosti:

```python
inferred_option_id = None
```

### Motive hypotheses

- največ tri;
- niso ground truth;
- lahko vsebujejo več konkurenčnih razlag;
- če ni podprte razlage:

```python
motive_hypotheses = ()
motive_unknown_reason = "..."
```

- model ne sme biti kaznovan, ker noče ugibati nevidnega;
- model mora biti kaznovan za samozavestno nepodprto razlago.

### Confidence

Loči:

```text
action_confidence
option_confidence
confidence vsake motive hypothesis
```

Ne uporabljaj več enega samega confidence za vse tri.

## 7.6 Promptni epistemološki contract

System prompt mora jasno povedati:

```text
Ti simuliraš zavestno Racijevo interpretacijo omejenega signala.
Ne vidiš notranjega sklepa Emocia ali Instinkta.
Ne poznaš pravega motiva.
Ne vidiš karakterja.
Ne vidiš evaluatorjevega golda.
Ne smeš enačiti akcije z motivom.
Ne smeš uporabiti besedila možnosti kot dokaza o signalu, ki ni manifestiran.
Vsaka trditev mora citirati vidno observation.
Ko signal ne določa optiona, abstiniraj.
Ko motiv ni določljiv, vrni prazen seznam hipotez in razloži neznanko.
```

V promptu ne zapiši:

```text
pravilen motiv je ...
```

Ne vgradi vseh gold pravil kot if/then lookup tabelo.

## 7.7 Simetrični pass audit

Pred modelnim klicem izberi 8–12 obstoječih pass zapisov z determinističnim pravilom.

Predlagana stratifikacija:

```text
2 jasna Emocio pass primera
2 jasna Instinkt pass primera
2 ambiguous/abstention pass primera
2 bilingual pair pass primera
po možnosti 2 dodatna primera z visoko confidence
```

Izbor mora biti določen pred branjem outputov, na primer:

```text
leksikografsko prvi passing case iz vsake kategorije
```

Za vsak primer preveri:

- ali je option res določljiv;
- ali je action neposredno podprt;
- ali je motive exact res upravičen;
- ali je confidence primeren;
- ali bi v2 pass ostal epistemološko dober;
- ali je model morda samo zadel gold.

Poročilo:

```text
Docs/evals/research_reset_2026-07/c3_pass_symmetry_audit.md
```

Največ eno poročilo.

Ne spreminjaj v1 scorea.

## 7.8 Evaluator v2

Predlagana lokacija:

```text
app/backend/rei/evaluation/racio_epistemic.py
```

Ločene dimenzije:

```text
structural_validity
citation_scope
hidden_truth_leakage
profile_leakage
action_support
option_determinacy
option_mapping
motive_support
motive_hypothesis_coverage
unsupported_motive_overclaim
abstention_quality
confidence_calibration
bilingual_semantic_consistency
```

V2 ne sme imeti enega samega glavnega exact boolean scorea.

Lahko ima:

```text
hard_contract_pass
research_metrics
```

Toda research_metrics ostanejo ločene.

## 7.9 G1 testi

Najmanj:

```text
test_action_does_not_imply_motive
test_option_text_cannot_create_hidden_signal
test_same_action_different_motive_is_valid
test_same_action_two_modalities_requires_option_abstention
test_motive_hypotheses_are_cited
test_motive_hypotheses_max_three
test_unknown_motive_requires_reason
test_confidences_are_separate
test_v1_schema_and_hash_remain_unchanged
test_character_is_absent_from_v2_packet
```

## 7.10 G1 commit

```text
feat(racio): add epistemic interpretation contract and evaluator v2
```

---

# 8. G2 — Gemma 4 31B lokalni preflight

## 8.1 Brez tihega prenosa

Najprej preveri:

```powershell
ollama list
ollama show gemma4:31b
```

Če runtime teče v WSL:

```powershell
wsl ollama list
wsl ollama show gemma4:31b
```

Če model ni nameščen:

- ne uporabi `gemma4:latest`;
- ne uporabi cloud različice;
- ne izberi drugega modela;
- ne začni avtomatskega 20 GB prenosa brez jasnega zapisa;
- poročaj uporabniku in navedi točen pull command.

## 8.2 Zabeleži model identity

Obvezno:

```text
model tag
model digest
quantization
parameter size
serialized size
Ollama version
runtime endpoint
context capability
supported modalities
template/system-role support
```

Lokalni digest je source of truth.

## 8.3 Začetni runtime profil

Za prvi razvojni screen uporabi:

```text
model: gemma4:31b
endpoint: local only
num_ctx: 65536
num_gpu: 999
require_full_gpu: true
seed: 314159
temperature: 0.0
top_p: 0.95
top_k: 64
num_predict: 2048
stream: false
raw: false
keep_alive: 10m
fallback: none
retry: none
format: RacioEpistemicInterpretationV2 JSON schema
```

Zakaj `temperature=0`:

- naloga zahteva stabilen strukturiran output;
- ne izvajamo ustvarjalnega pisanja;
- kasnejša sampling ablation je dovoljena samo na development setu in samo po G3 pregledu.

## 8.4 Thinking mode

Gemma 4 ima poseben thinking način.

Za prvi screen:

- uporabi thinking;
- system prompt naj začne z:

```text
<|think|>
```

- preveri, ali lokalni Ollama vrne thinking ločeno od final response;
- evaluator sme obravnavati samo final structured output;
- thinking vsebine ne pošiljaj v naslednji turn;
- thinking vsebine ne uporabljaj kot evidence;
- v research artefakt zapiši samo:
  - ali je bila prisotna,
  - byte/token count, če je dosegljiv,
  - SHA-256;
- ne shranjuj celotnega thinking besedila v Git;
- ne zahtevaj chain-of-thoughta v output schemi.

Če lokalna različica ne podpira ločenega thinking polja:

- ne ugibaj;
- ne parsaj ročno notranjih tagov kot semantični output;
- izvedi en tehnični probe;
- poročaj;
- ne preklopi tiho na drug model.

## 8.5 Full GPU

Po prvem tehničnem klicu preveri:

```powershell
wsl ollama ps
```

Zahtevaj:

```text
gemma4:31b
context 65536
100% GPU
```

Če ni 100% GPU:

- ne spreminjaj semantičnega prompta;
- najprej poročaj o runtime problemu;
- ne nadaljuj v celoten screen brez uporabnikove odločitve, če bi bil run bistveno počasnejši ali drugačen od dogovorjenega.

## 8.6 Provider

Ne spreminjaj zamrznjenega Qwen providerja.

Dodaj tanek v2 adapter:

```text
app/backend/rei/providers/ollama_gemma4_epistemic.py
```

Ali uporabi generični obstoječi provider samo, če to ne spremeni v1 hashov in obnašanja.

Provider mora:

- sprejeti samo sanitized conscious packet v2;
- ne videti native trutha;
- ne videti profila;
- ne videti character authority;
- ne videti expected outputa;
- ne imeti fallbacka;
- beležiti digest in GPU placement;
- validirati JSON schema;
- vrniti final output in ločen thinking metadata record.

## 8.7 G2 tehnični probe

En sam trivialni development packet.

Preveri:

- model se naloži;
- full GPU;
- system role;
- thinking separation;
- JSON schema;
- Slovenian Unicode;
- citation IDs;
- no extra fields;
- no retry.

Ta probe ne šteje v semantični score.

## 8.8 G2 commit

```text
feat(racio): add pinned local Gemma 4 epistemic provider
```

---

# 9. G3 — omejen Gemma razvojni screen

## 9.1 Namen

G3 ni holdout in ni generalization claim.

Njegovo vprašanje je:

> Ali Gemma 4 31B ob epistemološko pravilnejšem outputu daje bolj uporabne, manj samozavestno napačne Racijeve interpretacije?

## 9.2 Corpus

Uporabi 8 človeško pregledanih semantic roots, vsak v slovenščini in angleščini:

```text
8 roots × 2 jezika = 16 model calls
```

Predlagani rooti:

1. H1 — desired scene mismatch + connect;
2. H3 — desired scene absent + protect;
3. H7 — recurrent broken scene + set_boundary;
4. H11 — boundary alarm + seek_safety;
5. H15 — ista meja, verbalno ali fizično;
6. R1 — anger + attack, option nedoločljiv;
7. R3 — attachment pull + seek_attachment;
8. R5 — attraction + perform motor step.

## 9.3 Naturalizacija inputa

Ne pošiljaj Gemmi samo že rešenih oznak:

```text
structured_tendency:connect
structured_tendency:protect
structured_tendency:seek_attachment
```

Za G3 pripravi razvojne **naturalized manifestation** variante.

Primer:

Namesto:

```json
{"signal_name":"motor_urge","value":"structured_tendency:connect"}
```

uporabi nekaj v smislu:

```json
{
  "signal_name": "motor_urge",
  "visible_description": "prisoten je impulz, da se oseba približa skupini in vzpostavi stik",
  "perception_status": "clear"
}
```

Namesto:

```json
{"signal_name":"boundary_alarm","value":0.92}
```

uporabi kombinacijo:

```text
močna telesna pripravljenost ustvariti razdaljo
napetost ob prestopu osebnega prostora
ni podatka, ali naj bo odziv beseden ali telesen
```

Pravila:

- vsebina ostane source-grounded;
- ne doda skritega motiva;
- ne doda golda;
- ne doda karakterja;
- ne vgradi option ID-ja v opis signala;
- slovenska verzija je kanonična;
- angleška je operational gloss;
- pare preglej pred modelnim runom;
- corpus je development-visible in se pozneje ne sme imenovati untouched holdout.

## 9.4 Precommit run manifest

Pred prvim od 16 klicev zamrzni:

```text
case order
case hashes
prompt hash
schema hash
model digest
runtime parameters
seed
expected number of calls
no-retry policy
```

Ne zahtevaj main-only ali forenzičnega copy-only okolja.

Uporabi zaupanja vredno lokalno okolje.

## 9.5 Točno 16 klicev

- en klic na case;
- brez retryja;
- brez fallbacka;
- brez popravka prompta po prvem outputu;
- brez spreminjanja golda;
- brez Qwen klica;
- brez temperature ablation;
- brez drugega seeda;
- brez VLM slik;
- brez avtomatske promocije.

## 9.6 Poročilo

```text
Docs/evals/research_reset_2026-07/gemma4_racio_epistemic_dev_screen.md
```

Ločeno prikaži:

### Struktura

- valid JSON;
- citation scope;
- hidden leakage;
- profile leakage;
- input immutability.

### Action

- direct action cue correctly interpreted;
- unsupported action;
- action abstention.

### Option

- unique option mapping;
- underdetermined option abstention;
- option overcommit.

### Motive hypotheses

- supported hypothesis;
- unsupported hypothesis;
- hierarchy compatibility;
- missing plausible hypothesis;
- overconfident single hypothesis;
- useful alternative set.

### Confidence

- direct signal;
- overlap;
- underdetermined;
- unsupported claim.

### Jezik

- option consistency;
- action consistency;
- motive-family consistency;
- evidence consistency;
- confidence delta.

Ne izračunaj enega skupnega `REI score`.

## 9.7 Človeški review

Codex lahko izračuna tehnične in vnaprej opredeljene semantične metrike.

Codex ne sme sam podeliti:

```text
semantic authority
production authority
default model status
```

Pripravi tabelo za uporabnika:

```text
case
visible signal
Gemma reading
action
option
motive hypotheses
uncertainty
confidence
audit note
human decision
```

## 9.8 G3 stop kriteriji

Po reportu se obvezno ustavi.

Ne nadaljuj v G4/G5, tudi če je rezultat zelo dober.

## 9.9 G3 commit

```text
feat(eval): run bounded Gemma 4 Racio epistemic screen
```

Generated raw outputs lahko ostanejo pod `output/` in zunaj Gita; v Git shrani sanitized report in manifest hash.

---

# 10. Odločitveno drevo po G3

Ta razdelek ni dovoljenje za avtomatsko nadaljevanje.

## 10.1 Če Gemma ne validira JSON

Problem je:

```text
provider / schema / prompt formatting
```

Ne:

```text
REI teorija
motivna ontologija
modelna inteligenca
```

Dovoljen naslednji korak je samo tehnični popravek in nov majhen smoke, ne celoten rerun.

## 10.2 Če action deluje, motive hypotheses pa ne

Najprej preveri:

- ali je motiv v vidni manifestaciji sploh določljiv;
- ali je taxonomy preozka;
- ali model enači action z motivom;
- ali naturalized signal vsebuje dovolj informacij;
- ali evaluator zahteva hidden truth.

Ne menjaj modela avtomatsko.

## 10.3 Če model pravilno abstinira, a stari gold zahteva option

To je verjetno evaluator/corpus problem.

Ne označi Gemme za slabšo samo zato, ker je epistemološko bolj poštena.

## 10.4 Če slovenščina odstopa

Najprej primerjaj:

- semantično enakovrednost inputov;
- terminologijo;
- implicitne glagolske razlike;
- prevod `boundary`, `attachment`, `protect`, `withdraw`, `scene`.

Ne preklopi canonical jezika v angleščino.

Slovenščina ostane source of truth.

## 10.5 Če je Gemma obetavna

Naslednji korak je G4:

```text
nov untouched holdout v2
```

Ne modelna integracija.

---

# 11. G4 — nov untouched holdout v2

**Šele po izrecnem uporabnikovem dovoljenju.**

## 11.1 Nova veja

Po pregledu G3:

```text
codex/racio-gemma4-holdout-v1
```

Base je pregledani Gemma development branch ali po uporabnikovi odločitvi posodobljeni `main`.

## 11.2 Velikost

```text
12 novih semantic roots
× 2 jezika
= 24 cases
```

## 11.3 Vsebinski balans

Najmanj:

```text
4 Emocio clear manifestation roots
4 Instinkt clear manifestation roots
2 overlap/hierarchy roots
2 underdetermined/abstention roots
```

Obvezne vrste:

- desired scene absent;
- desired scene mismatch;
- actual broken scene;
- visual vs motor Emocio;
- connect brez avtomatske attachment oznake;
- set_boundary iz Emocieve scene;
- set_boundary iz Instinktove meje;
- attachment/loss;
- resource/scarcity;
- trust;
- escape availability;
- ista akcija, dve različni poti;
- dve možnosti, ista akcija, modalnost ni vidna.

## 11.4 Novi primeri

Prepovedano:

- parafrazirati iste stare root-e;
- kopirati option strukturo H1–H15 ali R1–R11;
- uporabljati stare case IDs;
- vpisati `structured_tendency:*` kot glavni odločilni cue;
- v opis optiona skriti edini dokaz motiva;
- označiti poddeterminiran primer kot unambiguous;
- določiti karakter;
- ustvarjati training export.

## 11.5 Gold v2

Gold ne vsebuje samo ene exact motive oznake.

```python
class EpistemicGoldV2:
    option_determinacy: Literal["unique", "underdetermined"]
    acceptable_option_ids: tuple[str, ...]
    expected_action_tendencies: tuple[str, ...]
    action_support_level: Literal["direct", "inferable", "unknown"]

    acceptable_motive_hypotheses: tuple[GoldMotiveHypothesis, ...]
    motive_support_level: Literal[
        "unique",
        "overlapping",
        "hierarchical",
        "not_identifiable",
    ]

    maximum_option_confidence: float | None
    maximum_motive_confidence: float | None
    required_abstention: bool

    forbidden_inferences: tuple[str, ...]
    source_claim_ids: tuple[str, ...]
```

## 11.6 Človeški precommit review

Pred modelnim klicem mora uporabnik ali določen reviewer potrditi:

- da je vsaka slovenska površina jasna;
- da angleški gloss ohranja pomen;
- da option determinacy drži;
- da action in motive nista zlita;
- da motive gold izhaja iz vidnega;
- da poddeterminirani primeri dovoljujejo abstention;
- da ni character leakage.

Šele nato se manifest zapečati.

## 11.7 En uradni Gemma run

- 24 klicev;
- isti model digest;
- isti runtime profil, izbran po G3;
- brez retry;
- brez fallback;
- brez prompt spremembe;
- brez Qwen runa;
- brez spremembe golda.

## 11.8 Hard gates

Obvezno:

```text
24/24 valid schema
0 hidden-ground-truth leakage
0 profile leakage
0 input mutation
0 out-of-scope citations
100% abstention na required-abstention primerih
0 izbire optiona izključno iz hidden ali option-text-only motiva
```

## 11.9 Raziskovalne metrike

Poročaj ločeno:

```text
direct action accuracy
unique option accuracy
motive top-k coverage
unsupported motive overclaim count
hierarchy-compatible motive coverage
bilingual semantic consistency
confidence calibration
alternative-hypothesis usefulness
```

Predlagani začetni cilj, ne absolutni produkcijski gate:

```text
direct action >= 90%
unique option >= 85%
motive top-k coverage >= 85%
unsupported motive overclaims <= 1
bilingual semantic consistency >= 90%
```

Če eden od ciljev ni dosežen, ne pomeni avtomatskega zavrženja modela. Naredi failure analysis.

---

# 12. G5 — Gemma kot multimodalni Racio nad Emocievimi slikami

**Šele po uspešnem tekstovnem holdoutu ali izrecni uporabnikovi odločitvi.**

## 12.0 Potrjena meja implementacije slik — 2026-07-23

Pregled Emocievih slik v GUI-ju se ne implementira v predhodni tekstovni
shadow fazi in se ne dodaja kot samostojen read-only image replay.

Implementacija slikovnega pregleda je del te faze G5. GUI mora biti izdelan
skupaj z Gemma vision potjo in mora jasno pokazati Emocievo sliko, exact vision
input, Gemmin vision odgovor, validacijo ter no-authority diagnostično
primerjavo. Pred G5 se nobena slika ne sme prikazovati kot nekaj, kar je Gemma
videla pri tekstovnem klicu.

Ta zapis ne dovoljuje začetka G5 ali novih modelnih klicev.

## 12.1 Namen

Gemma 4 31B podpira sliko in tekst.

To omogoča:

```text
Emocio ustvari notranjo sliko
        ↓
Racio jo pogleda
        ↓
Racio jo interpretira
```

To je konceptualno skladno z REI samo, če ostanejo meje pravilne.

## 12.2 Modelne vloge

```text
LongCat = Emocievo vizualno platno / image editor
Gemma 4 = Racijev vizualni interpreter
```

Prepovedano:

```text
Gemma 4 odloča namesto Emocia
Gemma 4 popravlja Emociev native option
Gemma 4 vidi prompt, iz katerega je bila slika generirana
Gemma 4 vidi filename enter_circle/remain_edge
Gemma 4 vidi expected option
```

## 12.3 Prvi corpus

Uporabi samo človeško sprejete LongCat pare:

```text
root 424240
root 424242
```

ker imata oba sprejet ENTER in REMAIN.

## 12.4 Opaque artefakti

Pred VLM klicem:

- kopiraj sliko v opaque artifact ID;
- odstrani semantični filename;
- odstrani prompt iz metadata;
- ne posreduj source option labela;
- randomiziraj vrstni red slik;
- zabeleži mapping samo v evaluator-only gold.

## 12.5 Tri ablation modes

```text
structured_only
image_only
structured_plus_image
```

Za vsako sliko oziroma par preveri:

- ali Racio vidi razliko med prihodnjima prizoroma;
- ali pravilno mapira javno možnost;
- ali iz slike izmišljuje skriti motiv;
- ali structured signal izboljša ali poslabša interpretacijo;
- ali je confidence umerjen.

## 12.6 Vrstni red modalnosti

Pri Gemma inputu:

```text
image first
text second
```

## 12.7 Slika ni external evidence

Generated image ostane:

```text
internal Emocio artifact
```

Ne postane:

```text
SceneEvent external fact
```

Gemmina opažanja o renderer-added podrobnostih morajo biti označena kot:

```text
image-observed, not externally grounded
```

---

# 13. G6 — integracija v runtime

**Šele po uporabnikovem sprejemu holdouta.**

## 13.1 Defaulti

Deterministični runtime ostane default.

Model-backed način se omogoči izrecno:

```text
REI_RACIO_INTERPRETER_PROVIDER=gemma4
REI_RACIO_INTERPRETER_MODEL=gemma4:31b
```

Brez tihega modelnega klica.

## 13.2 Brez fallbacka

Če Gemma odpove:

```text
model-backed cycle fails visibly
```

Ne:

```text
Gemma -> Qwen
Gemma -> deterministic
Gemma -> hidden heuristic
```

Deterministični mode se izbere pred ciklom, ne kot prikriti fallback.

## 13.3 Ego zapis

EgoMeasure lahko zapiše:

```text
visible manifestations
Racio action reading
Racio option mapping
Racio motive hypotheses
unresolved ambiguity
later evaluator TranslationGap
```

Motive hypotheses niso native truth.

## 13.4 GUI

Prikaži ločeno:

```text
What Racio saw
What Racio inferred directly
Which option Racio selected or rejected
Motive hypotheses
Uncertainty
Evaluator-only native truth (debug only)
```

Jasno opozorilo:

```text
Racio ni prejel native ground trutha.
```

---

# 14. Kaj ostane izven obsega

Ta načrt ne dovoljuje:

- Gemme kot Emocieva procesorja;
- Gemme kot Instinktovega telesnega mapperja;
- Gemme kot Ega;
- Gemme kot character detectorja;
- ugotavljanja značaja resničnih oseb;
- psiholoških diagnoz;
- medicinskih sklepov;
- LifeAgent;
- QLoRA;
- LoRA;
- SFT;
- training datasetov;
- model judgea kot edine resnice;
- ensemble modelov;
- production deploymenta;
- model promotion brez untouched holdouta.

---

# 15. Omejitev obsega prvih faz

Za G0–G3 skupaj brez nove odobritve:

```text
največ 5 funkcionalno novih/spremenjenih source datotek
največ 3 nove/spremenjene testne datoteke
največ 2 poročili poleg obstoječega audita
največ 1 novi development corpus
največ 17 Gemma klicev:
- 1 tehnični probe
- 16 development cases
```

Če Codex potrebuje več:

- ne razširi obsega sam;
- poročaj;
- počakaj.

Ne gradi novega generičnega benchmark frameworka, če lahko uporabi obstoječega s tankim v2 slojem.

---

# 16. Predlagane datoteke G0–G3

```text
Docs/evals/research_reset_2026-07/c3_failure_audit.md
Docs/evals/research_reset_2026-07/c3_pass_symmetry_audit.md
Docs/evals/research_reset_2026-07/gemma4_racio_epistemic_dev_screen.md
Docs/evals/research_reset_2026-07/research_log.md
CURRENT.md

app/backend/rei/communication/epistemic_interpreter.py
app/backend/rei/evaluation/racio_epistemic.py
app/backend/rei/providers/ollama_gemma4_epistemic.py

scripts/run_gemma4_racio_epistemic_dev.py

tests/evaluation/test_racio_epistemic_contract.py
tests/evaluation/test_gemma4_epistemic_provider.py
tests/evaluation/test_gemma4_epistemic_dev_runner.py

knowledge/canon_v2/open_questions.md
knowledge/canon_v2/semantic_lab_v1/gemma4_epistemic_dev_v1/
```

Ne ustvarjaj vseh datotek, če niso potrebne. Preferiraj manjši vertikalni rez.

---

# 17. Predlagani commit plan

## Commit 1

```text
docs(racio): accept X2 audit amendments and select Gemma 4 31B
```

## Commit 2

```text
feat(racio): add epistemic interpretation contract and evaluator v2
```

## Commit 3

```text
feat(racio): add pinned local Gemma 4 epistemic provider
```

## Commit 4

```text
feat(eval): run bounded Gemma 4 Racio epistemic screen
```

Po commitu 4:

- push feature vejo;
- ne odpiraj PR-ja;
- ne mergeaj;
- ustavi se.

---

# 18. Obvezni report po G3

```text
Phase: G0–G3
Branch:
Base branch:
Base SHA:
Head SHA:

Human audit decision recorded:
H3 amendment:
H7 amendment:
H11 amendment:
Pass symmetry cases reviewed:

Model:
Model tag:
Model digest:
Ollama version:
Quantization:
Serialized size:
Context:
GPU placement:
Thinking mode:
Temperature:
Seed:
Schema hash:
Prompt hash:

Technical probe:
Development corpus:
Gemma model calls:
Retries:
Fallbacks:

Structural validity:
Citation validity:
Hidden leakage:
Profile leakage:
Input mutation:

Action results:
Option results:
Abstention results:
Motive hypothesis results:
Unsupported motive overclaims:
Confidence observations:
Slovenian/English consistency:

Comparison with frozen Qwen:
- only qualitative/dimensional;
- no retroactive rescore.

Generated artifacts:
Report paths:
Tests run:
Tests passed:
Tests failed:

Semantic authority: no
Production authority: no
Default runtime promotion: no
PR opened: no
Merged to main: no

Human questions:
1.
2.
3.

Next possible decision:
- revise ontology/input
- proceed to untouched holdout
- reject Gemma for this role
- run a bounded sampling/thinking ablation on development cases only
```

---

# 19. Definition of success za G0–G3

Prvi Gemma sklop je uspešen, če:

- stari Qwen rezultat ostane nespremenjen;
- failure audit dobi človeško odločitev;
- H3, H7 in H11 so pravilno popravljeni;
- pass audit preveri tudi uspešne primere;
- v1 schema in evidence ostanejo nedotaknjeni;
- action, option in motive hypotheses so ločeni;
- option descriptions ne ustvarjajo skritega motiva;
- Gemma je pinana na exact digest;
- Gemma teče lokalno in na GPU;
- structured final output je validen;
- thinking ni pomešan s final outputom;
- izvedenih je največ 17 klicev;
- rezultat je človeško pregledljiv;
- Codex se po G3 ustavi;
- model ni avtomatsko promoviran.

---

# 20. Dolgoročni cilj

Uspešna smer mora pripeljati do tega:

```text
Emocio ali Instinkt izdela svoj nativni sklep.

Racio ne vidi tega sklepa.
Vidi samo manifestacijo.

Racio pravilno prepozna del signala.
Nekaj lahko razume.
Nekaj lahko napačno razloži.
Nekaj mora pustiti odprto.

Gemma 4 ne deluje kot oracle skritega motiva,
ampak kot bolj ali manj zanesljiv zavestni interpreter.

Karakter nato določi oblast med že nastalimi sklepi.

ConsciousDecision ostane Racijeva.
BehaviorResultant lahko odstopa.
Ego zapiše celotno skladbo in prevajalsko vrzel.
```

To je merilo napredka. Ne število testov, hashov ali modelnih klicev.
