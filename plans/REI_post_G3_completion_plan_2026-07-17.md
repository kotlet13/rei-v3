# REI-v3 — nadaljevanje po G3: od semantičnega audita do dokončane infrastrukture

**Namen:** izvedbeni načrt za Codex po zaključenem Gemma 4 G3 razvojnem screenu
**Repozitorij:** `kotlet13/rei-v3`
**Aktivna veja:** `codex/racio-gemma4-epistemic-interpreter`
**G3 pre-call seal:** `d9027d97faec36f1d2c806a5efe5e935ed931014`
**G3 rezultatni commit:** `72f05d7`
**Datum:** 2026-07-17
**Cilj:** dokončati in sistemsko preizkusiti celotno REI infrastrukturo, ne da bi modelno kakovost zamenjali za arhitekturno pravilnost ali obratno.

---

# 0. Človeška odločitev po G3

G3 je sprejet kot **uspešen razvojni eksperiment**, vendar ne kot promocija Gemme.

Sprejeto:

- transport in provider pogodba delujeta;
- 16/16 klicev je tehnično uspelo;
- 16/16 izhodov je strukturno veljavnih;
- hidden-truth in profile leakage nista bila zaznana;
- vseh 12 določljivih možnosti je bilo pravilno preslikanih;
- vsi 4 primeri, kjer možnost ni bila določljiva, so pravilno abstinirali;
- option bilingual consistency je 8/8;
- Racijeva samoocena negotovosti je strukturno delovala in je bila dvojezično skladna v 7/8 parih.

Ni sprejeto:

- action interpretation kot dovolj zanesljiv semantični sloj;
- motive precision;
- slovensko-angleška stabilnost akcijskih oznak;
- Gemma kot privzeti ali aktivni RacioInterpreter;
- runtime vpliv Gemmine interpretacije na `ConsciousDecision` ali `BehaviorResultant`;
- kakršenkoli skupni semantic pass.

Ključna diagnoza G3:

```text
Gemma zelo dobro razume, katera javno podana možnost ustreza vidnemu signalu,
in pravilno abstinira, ko tega ni mogoče vedeti.

Slabše pa prevaja isti signal v trenutno ravno akcijsko taksonomijo
in prepogosto navede dodatne motive, ki niso dovolj podprti.
```

To pomeni, da G3 ni razlog za zavrnitev Gemme. Je razlog, da pred novim holdoutom popravimo **mejo med opazovanim, akcijsko klasifikacijo in motivno hipotezo**.

---

# 1. Nespremenljivi REI invarianti

Codex naslednjih pravil ne sme spreminjati.

## 1.1 Racio

- Racio je edini neposredno zavestni razum.
- `RacioNative`, `RacioInterpreter`, `RacioCommitter` in `RacioNarrator` so ločene funkcije.
- RacioInterpreter vidi samo zavestno dostopne manifestacije.
- Ne vidi skritega `EmocioNativeConclusion`, `InstinktNativeConclusion`, native motiva ali evaluatorjevega golda.
- Vsaka interpretacija je hipoteza Racia, ne neposredna resnica drugega razuma.
- `ConsciousDecision.made_by == "R"` ostane invariant.

## 1.2 Emocio

- Emocio nativno procesira prizore, slike, mozaike, vidnost, pripadnost, privlačnost, tekmovanje in gibanje.
- Njegov nativni sklep nastane pred Racijevo interpretacijo.
- Current scene, desired scene, broken scene in option rollouts ostanejo ločeni.
- Renderirana slika je notranji artefakt in ne external evidence.

## 1.3 Instinkt

- Instinkt nativno procesira telo, nevarnost, izgubo, mejo, zaupanje, navezanost, pomanjkanje in umik.
- Njegov nativni sklep nastane pred verbalizacijo.
- Telesni signal ne spremeni karakterja.
- Instinktov rezultat ni medicinska diagnoza.

## 1.4 Karakter

- Karakter je stabilna ordinalna hierarhija.
- Intenzivnost, confidence, stres in trenutna aktivacija ne spreminjajo `CharacterAuthority`.
- Profil se ne pošilja nativnim procesorjem.
- Parni značaj nima podrejenega tie-breakerja.
- `R=E=I` uporablja 2-of-3.
- `simulated_spoznanje` zahteva isti sklep vseh treh.

## 1.5 Ego

- Ego ni agent in nima vote API-ja.
- `EgoMeasure` je en cikel.
- `EgoTrace` je append-only zgodovina.
- `EgoCompositionSnapshot` je izpeljan model ponavljajočih se motivov in napetosti.
- `EgoReflector`, če je uporabljen, je read-only analitik.

---

# 2. Najpomembnejši popravek po G3

Trenutna pogodba še vedno deloma meša tri različne ravni:

```text
A. Kaj je v manifestaciji neposredno vidno?
B. Kakšna je funkcionalna akcijska smer?
C. Kaj je možen motiv v svetu Emocia ali Instinkta?
```

G3 kaže, da jih moramo strožje ločiti.

## 2.1 Opazovani signal

Primer:

```text
"Prisoten je jasen impulz približati se skupini in vzpostaviti stik."
```

To neposredno podpira površinski opis:

```text
približevanje + stik
```

Ne določa nujno samo ene programske oznake:

```text
approach
connect
seek_attachment
```

`connect` in `approach` sta lahko različni ravni iste akcijske družine. Zato trenutni exact enum gate lahko označi smiseln odgovor kot napačen.

## 2.2 Akcijska družina in podtip

Uvedi zamenljivo implementacijsko hipotezo:

```text
approach_engage
├── approach
├── connect
├── seek_attachment
└── perform_toward_target

protection_regulation
├── protect
├── set_boundary
├── seek_safety
├── withdraw
├── freeze
└── conserve

confrontation
├── attack
├── compete
└── remove_obstacle

execution_expression
├── perform
├── improvise
└── coordinate
```

To ni nov kanon REI. Je programska taksonomija za primerjavo odgovorov.

Vsak evaluator mora zato ločeno oceniti:

```text
action_family_support
action_subtype_support
```

## 2.3 Motiv

Motiv ni akcija.

Prepovedani sklepi:

```text
set_boundary -> boundary_alarm
connect -> attachment
protect -> body_alarm
perform -> attention/status
```

Akcija je lahko posledica več poti. Motivna hipoteza mora citirati manifestacijo, ki podpira motiv, ne samo izbrano akcijsko oznako.

## 2.4 Minimalnost hipotez

G3 je dosegel pričakovani motiv v 15/16 primerih, vendar je dodal 15 nepodprtih hipotez v 10 primerih.

To kaže, da je trenutna naloga preveč naklonjena naštevanju možnosti.

Nova referenčna Racijeva disciplina:

```text
- 0 hipotez, kadar motiv ni razviden;
- 1 primarna hipoteza, kadar jo neposredno podpira signal;
- 2. ali 3. hipoteza samo, če ima vsaka ločeno, citirano oporo;
- sama splošna možnost ni zadosten razlog za vključitev;
- nižja confidence ne spremeni nepodprte hipoteze v podprto.
```

---

# 3. Dva ločena cilja: infrastruktura in raziskovalna kakovost

Nadaljnje delo se razdeli na dve vzporedni, jasno ločeni sledi.

## Sled A — dokončanje infrastrukture

Cilj:

```text
vsi procesorji, providerji, runtime načini, GUI, shranjevanje,
fail-closed poti, end-to-end demonstracije in longitudinalni Ego delujejo
```

Infrastruktura je lahko dokončana, tudi če Gemma še ni raziskovalno promovirana.

## Sled B — raziskovalna kakovost modelov

Cilj:

```text
izmeriti, koliko dobro posamezen model interpretira manifestacije,
kako stabilen je med jeziki in kje sistematično racionalizira ali pretirava
```

Modelna kakovost ne sme blokirati tehnične integracije v `shadow` načinu. Ne sme pa biti prikrito razglašena za sprejeto.

---

# 3.1 Priporočeni dejanski vrstni red

Raziskovalna in infrastrukturna sled se prepletata v naslednjem vrstnem redu:

```text
G3A  človeško-semantična adjudikacija
G3B  pogodba/evaluator v3
I1   Gemma text shadow integracija brez odločitevne avtoritete
G3C  en zamrznjen rerun istega dev corpusa
G4   novi untouched holdout
I2   Gemma vision shadow
I3   Instinkt raw-scene mapper
I4   Ego untagged-story detector
I5   tri end-to-end demonstracije
I6   končni sistemski acceptance
```

Razlog: infrastrukture ne blokiramo do popolnega modela, vendar modela tudi ne
spustimo v aktivno odločanje, preden prestane nov holdout. Shadow integracija
omogoči, da se celotna pot, artefakti, GUI in failure handling dokončajo že prej.

# 4. Faza G3A — človeško-semantična adjudikacija G3

**Naslednja dovoljena faza.**
**Modelni klici: 0.**
**Runtime spremembe: 0.**

## 4.1 Namen

Pred vsakim promptnim ali evalvacijskim popravkom pregledati:

- vseh 8 action mismatchov;
- vseh 15 unsupported motive overclaimov;
- 6 primerov brez overclaimov;
- vseh 8 bilingual parov.

## 4.2 Za vsak action mismatch zapiši

```text
case_id
visible manifestation
expected subtype
model subtype
expected family
model family
classification:
  true_model_error
  acceptable_sibling
  acceptable_parent
  gold_too_narrow
  taxonomy_level_mismatch
  bilingual_translation_drift
  packet_ambiguity
human decision
```

Posebej preveri:

- H1 EN `approach` proti `connect`;
- H15 `protect` proti `set_boundary`;
- H7 `seek_safety` proti `set_boundary`;
- R1 SL `conserve` proti `attack`;
- R5 SL `seek_attachment` proti `perform`.

Prvih nekaj je lahko taksonomsko odstopanje; zadnja dva sta verjetneje prava semantična napaka. Tega ne vnaprej predpostaviti — pregled mora citirati packet.

## 4.3 Za vsak motivni overclaim zapiši

```text
case_id
hypothesis
citirani observations
directly_supported: yes/no
contextually_plausible: yes/no
derived_only_from_action_label: yes/no
family_relation_to_gold:
  same
  parent
  child
  sibling
  unrelated
classification:
  true_overclaim
  gold_too_narrow
  hierarchy_compatible
  language_drift
human decision
```

## 4.4 Simetrični pregled dobrih primerov

Ne pregleduj samo napak.

Obvezno preveri:

- H11 SL;
- R5 EN;
- oba H15 motiva;
- R1 SL unknown preservation;
- najmanj dva partially-supported primera brez action napake.

Cilj je preveriti, ali evaluator pravično ocenjuje tudi uspehe.

## 4.5 Bilingual analiza

Izračunaj posebej:

```text
SL action family support
EN action family support
SL action subtype support
EN action subtype support
SL unsupported overclaims
EN unsupported overclaims
```

G3 report kaže močan jezikovni učinek. Analiza mora ugotoviti, ali:

- Gemma bolje dekodira angleške akcije;
- angleščina hkrati sproža več motivnih overclaimov;
- slovenski opisi potrebujejo operativni angleški gloss;
- ali je problem v taksonomiji, ne jeziku.

## 4.6 Output

Ustvari samo:

```text
Docs/evals/research_reset_2026-07/g3_semantic_adjudication.md
```

Na koncu dokumenta morajo biti človeško potrjene odločitve:

```text
ACTION_TAXONOMY_DECISION
MOTIVE_MINIMALITY_DECISION
BILINGUAL_INPUT_DECISION
G3_RERUN_ALLOWED: yes/no
SHADOW_INTEGRATION_ALLOWED: yes/no
```

## 4.7 Prepovedi

- brez modelnih klicev;
- brez spremembe G3 artefaktov;
- brez retroaktivne spremembe originalnega G3 reporta;
- brez novega agregatnega scorea;
- brez spremembe providerja;
- brez G4 holdouta;
- brez mergea.

## 4.8 Commit

```text
docs(eval): adjudicate G3 action and motive semantics
```

Po commitu se ustavi.

---

# 5. Faza G3B — epistemološka pogodba v3

**Šele po človeški odobritvi G3A.**
**Modelni klici: 0.**

## 5.1 Nova shema

Ohrani v2 zgodovinsko nespremenjeno. Dodaj v3:

```python
class ActionHypothesis(BaseModel):
    family: str
    subtype: str
    cited_observation_ids: list[str]
    confidence: float
    support_mode: Literal[
        "direct_manifestation",
        "functional_inference",
        "speculative",
    ]

class MotiveHypothesis(BaseModel):
    family: str
    subtype: str
    cited_observation_ids: list[str]
    confidence: float
    support_mode: Literal[
        "directly_supported",
        "contextually_supported",
        "speculative",
    ]

class RacioEpistemicInterpretationV3(BaseModel):
    source_mind: Literal["E", "I"]
    cited_observation_ids: list[str]
    action_hypotheses: list[ActionHypothesis]
    inferred_option_id: str | None
    option_confidence: float
    motive_hypotheses: list[MotiveHypothesis]
    racio_reported_uncertainty: RacioReportedUncertainty
```

## 5.2 Pravila

- največ 2 action hypotheses;
- največ 3 motive hypotheses;
- `speculative` ne šteje kot podprt rezultat;
- preferiraj 0–1 motiv;
- option ostane ločen;
- action family/subtype ostaneta ločena;
- provider sidecar ostane samo strukturni;
- nobena hipoteza ne vpliva na governance.

## 5.3 Bilingual production packet

Dodaj možnost:

```python
BilingualObservation(
    canonical_sl="...",
    operational_en="...",
)
```

Pravila:

- `canonical_sl` je semantični source of truth;
- `operational_en` je pregledan gloss, ne dodatno evidence;
- oba imata isti observation ID;
- evaluator ve, da gre za isti signal;
- single-language mode ostane za stress test;
- production-candidate mode lahko uporablja oba.

## 5.4 Evaluator v3

Ločene metrike:

```text
action_family_coverage
action_subtype_coverage
action_unsupported_overclaims
option_mapping
required_abstention
motive_family_coverage
motive_subtype_coverage
motive_precision
high_confidence_unsupported_motives
unknown_preservation
bilingual_family_consistency
bilingual_subtype_consistency
uncertainty_consistency
```

Ne izračunaj enega REI scorea.

## 5.5 Testi

Obvezno:

- action parent/sibling/subtype primeri;
- action ni motiv;
- speculative motive ne šteje kot supported;
- bilingual gloss ne ustvari nove evidence;
- unknown motiv ostane dovoljen;
- hidden truth in profile leakage ostaneta 0;
- v2 artefakti se še vedno hladno validirajo.

## 5.6 Commit

```text
feat(eval): separate manifested action families from motive hypotheses
```

Po commitu se ustavi.

---

# 6. Faza G3C — en zamrznjen razvojni rerun

**Šele po odobritvi G3B.**

## 6.1 Namen

Preveriti, ali popravljena pogodba:

- zmanjša lažne action failureje;
- zmanjša motive overclaims;
- izboljša slovensko-angleško stabilnost;
- ne pokvari option mappinga in abstentiona.

## 6.2 Pravila

- isti 8 roots × 2 jezika = 16 klicev;
- isti model in digest;
- isti seed;
- isti runtime;
- ena zamrznjena v3 instrukcija;
- brez sprememb med klici;
- brez retryja;
- brez fallbacka;
- G3C je razvojni rerun, ne generalization evidence.

## 6.3 Poročilo

Pokaži v2 proti v3 po dimenzijah.

Ne prepiši originalnega G3.

## 6.4 Stop

Po 16 klicih se ustavi.

---

# 7. Faza G4 — nov untouched holdout

**Šele po človeškem pregledu G3C.**

## 7.1 Obseg

```text
12 novih roots × 2 jezika = 24 primerov
```

Vsi roots morajo biti novi in pred modelnim klicem zamrznjeni.

## 7.2 Pokritost

Najmanj:

- 3 jasni Emocio scene primeri;
- 2 motorična Emocio primera;
- 3 Instinkt protection primeri;
- 2 primera z isto akcijo in različnim motivom;
- 2 primera, kjer mora option abstain;
- 2 primera, kjer mora motiv ostati prazen;
- 2 hierarchical action primera;
- 2 parent/child motive primera;
- več primerov se lahko prekriva med kategorijami.

## 7.3 Predhodna zamrznitev

Pred prvim klicem zamrzni:

- corpus;
- gold;
- evaluator;
- provider revision;
- prompt;
- schema;
- model digest;
- call specs.

## 7.4 Začasni quality gate

Brez enega agregatnega scorea. Minimalni gate:

```text
Structural contract: 24/24
Hidden-truth leakage: 0
Profile leakage: 0
Required abstention: 100%
Unique option mapping: >= 11/12 roots
Option bilingual consistency: 12/12
Action family support: >= 10/12 roots
Action family bilingual consistency: >= 10/12 roots
Motive family coverage: >= 10/12 roots
Unknown preservation: 100%
High-confidence unsupported motive hypotheses (>=0.5): <= 2 across 24 cases
Motive family bilingual consistency: >= 9/12 roots
Uncertainty bilingual consistency: >= 10/12 roots
```

Če gate ni dosežen, Gemma ostane shadow-only. Infrastrukturno delo se lahko nadaljuje.

---

# 8. Faza I1 — Gemma text interpreter v shadow načinu

Ta faza je namenjena dokončanju infrastrukture in je dovoljena tudi, če Gemma še ni raziskovalno promovirana, vendar šele po G3A odločitvi.

## 8.1 Runtime načini

```python
RacioInterpreterMode = Literal[
    "deterministic",
    "gemma4_text_shadow",
    "gemma4_text_experimental",
    "gemma4_vision_shadow",
    "gemma4_vision_experimental",
]
```

Privzeto:

```text
deterministic
```

## 8.2 Shadow način

`gemma4_text_shadow`:

- požene Gemmo;
- shrani interpretacijo;
- izračuna TranslationGap v debug/eval sloju;
- prikaže rezultat v GUI;
- ne vpliva na `GovernanceMandate`;
- ne vpliva na `ConsciousDecision`;
- ne vpliva na `BehaviorResultant`;
- ne posodablja MindWorld;
- ob odpovedi cikel normalno nadaljuje z deterministic interpreterjem, vendar se odpoved jasno zabeleži kot shadow failure, ne kot silent fallback.

## 8.3 Artefakti

```text
communication/
├── deterministic_interpretation.json
├── gemma4_shadow_interpretation.json
├── shadow_comparison.json
└── provider_call_record.json
```

## 8.4 GUI

Prikaži:

- vidne manifestacije;
- deterministic interpretation;
- Gemma shadow interpretation;
- native truth samo v debug načinu;
- TranslationGap;
- opozorilo `NO DECISION AUTHORITY`.

## 8.5 Testi

- shadow output ne mutira native bundlea;
- shadow output ne mutira governance;
- shadow output ne mutira conscious decisiona;
- provider failure ne podre cikla;
- wrong digest fail-closed;
- invalid JSON fail-closed;
- timeout je zabeležen;
- deterministic rezultat ostane bitno enak z vklopljenim ali izklopljenim shadowom;
- GUI pravilno označi no-authority.

## 8.6 Commit

```text
feat(communication): integrate Gemma 4 Racio interpretation in shadow mode
```

---

# 9. Faza I2 — Gemma vision kot Racio, ki gleda Emocieve slike

## 9.0 Potrjena fazna meja za GUI slik — 2026-07-23

Implementacija pregleda Emocievih slik v GUI-ju se ne izvaja v tekstovni
shadow GUI fazi in se ne uvaja kot ločeni vmesni image-replay korak.

Celoten slikovni pregled se implementira šele v tej fazi I2, skupaj z Gemma
vision interpretacijo. Takrat mora GUI v eni jasno sledljivi poti prikazati:

```text
Emocieva slika
→ exact vision input, ki ga je prejel Racio
→ Gemma vision odgovor
→ validacija
→ diagnostična primerjava brez avtoritete
```

Do začetka I2 tekstovni shadow GUI prikazuje samo tekstovni modelni input in
mora izrecno povedati, da slika ni bila del klica. Slike se ne sme prikazati
na način, ki bi ustvarjal vtis, da jih je Gemma že videla.

Ta odločitev sama ne dovoljuje začetka I2 ali novih modelnih klicev. I2 ostane
za G4 po zapisanem vrstnem redu, razen če človek pozneje izrecno spremeni
vrstni red.

## 9.1 Vloga

```text
LongCat = Emocievo vizualno platno
Gemma 4 = Racio, ki vidi manifestirano sliko
```

Gemma ni Emocio.

## 9.2 Vhod

Gemma dobi:

- sliko;
- javni kontekst;
- javne možnosti, kadar so dovoljene;
- brez image prompta;
- brez option imena v filenameu;
- brez Emocievega native optiona;
- brez gold motiva;
- brez karakterja.

## 9.3 Prvi screen

Uporabi samo že človeško sprejete LongCat slike.

Najprej:

```text
4 roots × 2 možnosti × po potrebi 2 jezika
```

Cilj:

- prepoznati vidno dogajanje;
- ločiti približevanje od ostajanja ob robu;
- pravilno abstinirati glede skritega motiva;
- ne zamenjati vizualnega prizora za zunanjo resnico.

## 9.4 Shadow najprej

Vision interpreter naj bo najprej samo `gemma4_vision_shadow`.

---

# 10. Faza I3 — Instinkt raw-scene-to-body mapper

Trenutni Instinkt je transparenten effect-rules engine. Za dokončano infrastrukturo potrebuje še preslikavo surovega dogodka v cue-e.

## 10.1 Komponenta

```python
EmbodiedCueInterpreter
```

Vhod:

- SceneEvent;
- InstinktWorld;
- BodyState;
- option.

Izhod:

- candidate cues;
- evidence IDs;
- association IDs;
- negotovost;
- predicted body deltas;
- abstention.

## 10.2 Prvi test

10 novih dogodkov brez besed:

```text
strah, nevarnost, izguba, meja, zaupanje, pomanjkanje, navezanost, umik
```

Sistem mora dogodke razumeti iz situacije, ne iz oznake.

## 10.3 Runtime

Načini:

```text
manual_fixture
rule_based_auto
model_assisted_shadow
```

Privzeto ostane transparentna rule-based pot.

---

# 11. Faza I4 — Ego na neoznačeni zgodbi

## 11.1 Corpus

Ena ročno pripravljena zgodba:

```text
15 dogodkov
2 resnična ponavljajoča se motiva
5 distractorjev
2 lažni površinski podobnosti
3 Racijeve racionalizacije
3 Emocieve različne slike iste globlje želje
3 Instinktovi ponavljajoči se telesni odzivi
```

V dogodkih ne ponavljaj istih canonical tagov.

## 11.2 Načini

```text
structured_exact baseline
canonical_normalization
embedding_or_llm_shadow hypothesis
```

EgoReflector:

- samo predlaga motiv;
- citira measure IDs;
- ne odloča;
- ne piše neposredno v MindWorld;
- človek ali evaluator potrdi pred sprejemom.

---

# 12. Faza I5 — tri end-to-end demonstracije

## Demo A — Emocio vodi

```text
dogodek
→ current/desired/broken scene
→ LongCat rollouts
→ EmocioNativeConclusion
→ Gemma vision shadow interpretation
→ CharacterAuthority E>R>I
→ GovernanceMandate
→ Racio conscious decision
→ BehaviorResultant
→ EgoMeasure
```

## Demo B — Instinkt vodi

```text
surov dogodek
→ EmbodiedCueInterpreter
→ body rollouts
→ InstinktNativeConclusion
→ Gemma text shadow interpretation
→ CharacterAuthority I>R>E
→ ConsciousDecision
→ BehaviorResultant
→ EgoMeasure
```

## Demo C — komunikacijski šum

```text
native signal
→ manifestacija
→ Gemma pravilno prepozna option
→ napačno ali preširoko razloži motiv
→ RacioSelfNarrative racionalizira
→ TranslationGap
→ EgoTrace ohrani nerazrešeno napetost
```

---

# 13. Faza I6 — končni sistemski acceptance

## 13.1 Obvezni tehnični testi

- full test suite;
- 13-profile frozen-bundle matrix;
- deterministic end-to-end cycle;
- shadow Gemma text cycle;
- shadow Gemma vision cycle;
- LongCat provider failure;
- Ollama unavailable;
- wrong model digest;
- invalid JSON;
- timeout;
- partial GPU offload;
- renderer failure;
- Instinkt mapper abstention;
- Ego reflector failure;
- artifact store interruption;
- GUI smoke;
- archive rollback verification.

## 13.2 Obvezni raziskovalni artefakti

```text
Docs/evals/final/
├── racio_text_holdout.md
├── racio_vision_screen.md
├── instinkt_unseen_scenes.md
├── ego_untagged_story.md
├── three_end_to_end_demos.md
├── profile_matrix.md
└── infrastructure_acceptance.md
```

## 13.3 Definition of Done

Infrastruktura je dokončana, ko obstaja:

```text
✓ deterministic Racio, Emocio in Instinkt
✓ Gemma text shadow interpreter
✓ Gemma vision shadow interpreter
✓ optional experimental-active mode with explicit user opt-in
✓ LongCat visual rollout provider
✓ Instinkt raw-scene cue mapper
✓ ordinalna governance vseh 13 karakterjev
✓ conscious decision in behavior resultant
✓ TranslationGap
✓ append-only EgoTrace
✓ untagged motif shadow detector
✓ GUI za native / communication / character / Ego
✓ reproducibilni run manifests
✓ fail-closed provider paths
✓ 13-profile matrix
✓ 3 end-to-end demos
✓ 1 longitudinalni scenario
✓ full test suite
✓ rollback path
```

Ni potrebno, da je do takrat empirično dokazano:

- da REI drži kot psihološka teorija;
- da je Gemma najboljši model;
- da je motivna taksonomija dokončna;
- da so modelni odgovori vedno pravilni.

Potrebno je, da sistem te hipoteze pregledno izvaja, primerja, omejuje in testira.

---

# 14. Pravila proti ponovnemu vrtenju v krogu

1. Ena faza ne sme avtomatsko odpreti naslednje.
2. Model-free infrastruktura ni semantic pass.
3. Zeleni testi niso razlog za promocijo modela.
4. Ne ustvarjaj novega splošnega receipt sistema.
5. Ne refaktoriraj 1.500-vrstičnega Gemma providerja pred naslednjim semantičnim signalom, razen ob dejanski napaki.
6. G3 artefaktov ne prepisuj.
7. Dev corpus se po uporabi ne predstavlja kot holdout.
8. Ne prompt-tunaj med klici istega zamrznjenega runa.
9. Ne uvajaj QLoRA, LoRA ali SFT.
10. Ne podeljuj Gemmi governance authority.
11. Ne enači napačne Racijeve interpretacije z napako celotne REI arhitekture.
12. Ne enači realistične racionalizacije z referenčno epistemološko pravilnostjo — obe morata biti ločena runtime načina.

---

# 15. Neposredni naslednji korak

Izvedi samo G3A.

Po G3A se ustavi in počakaj na človeško odločitev o:

```text
- action hierarchy;
- motive minimality;
- bilingual packet;
- dovoljenju za shadow integracijo;
- dovoljenju za pogodbo v3.
```
