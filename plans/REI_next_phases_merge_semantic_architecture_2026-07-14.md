# REI-v3 — načrt integracije na `main` in naslednjih razvojnih faz

**Namen:** neposredno izvedbeno navodilo za Codex
**Repozitorij:** `kotlet13/rei-v3`
**Aktivna in edina dovoljena izvedbena veja:** `main`
**Predhodna integracijska veja:** `codex/architecture/rei-native-composition` (izključno zgodovinski podatek; že mergeana in se ne uporablja več)
**Temeljno pravilo:** vse nadaljnje faze, commiti in pushi potekajo neposredno na `main` oziroma `origin/main`; drugih vej se ne ustvarja, uporablja, objavlja ali obravnava kot izvedbeno alternativo
**Datum načrta:** 2026-07-14
**Status:** C8 integriran s tem faznim commitom neposredno na `main`; C7 tehnični contract gate uspešen, research-quality gate pa blokiran; pred C9 je potrebna kontrolirana image/model remediation
**Izven obsega:** QLoRA, SFT, LoRA trening, generiranje učnih datasetov in dokončna izbira produkcijskega modela

---

# 0. Namen naslednjega cikla

Prejšnja nadgradnja je uspešno zamenjala tekstovno arhitekturo treh LLM-procesorjev in `EgoResultant` z novo nativno kompozicijsko arhitekturo:

```text
Racio native
Emocio native
Instinkt native
        ↓
zamrznjeni NativeMindBundle
        ↓
ordinalna CharacterAuthority
        ↓
GovernanceMandate
        ↓
Racijeva interpretacija manifestacij
        ↓
ConsciousDecision
        ↓
BehaviorResultant
        ↓
EgoMeasure
        ↓
EgoTrace / EgoCompositionSnapshot
```

Naslednji razvojni cikel nima več naloge postavljati osnovne arhitekture. Njegov cilj je:

1. ohraniti sledljiv zapis že zaključene integracije sprejete arhitekture v `main`;
2. vzpostaviti semantični laboratorij, ki preverja, ali posamezni procesorji res sledijo REI-poti;
3. izdelati pravi Racijev interpretacijski sloj;
4. Emocia postopno premakniti iz strukturiranega simbolnega modela v pravo vizualno kognicijo;
5. Instinktu dodati samodejno, sledljivo preslikavo dogodka v telesne posledice;
6. Ego preizkusiti longitudinalno kot skladbo, ne samo kot enkratni zapis;
7. ohraniti deterministični, preverljiv baseline ob vsaki modelni nadgradnji.

To ni en sam velik commit. Codex mora vsako fazo izvajati ločeno in se po vsakem quality gateu ustaviti za pregled.

---

# 1. Zgodovinski predintegracijski posnetek repozitorija

Naslednji blok je zgodovinski posnetek pred zaključenim mergem in ni navodilo
za izbiro aktivne veje. Aktivna veja je `main`.

```text
base: main
head (historical): codex/architecture/rei-native-composition
status: diverged
ahead_by: 20
behind_by: 1
merge_base: 995b572c893058c82d265d978a0391e317f1ea67
main head: 07a26401e0b2707a79018efc2fdd7194d3062566
```

V takratnem posnetku je zgodovinski veji manjkal en dokumentacijski commit z
`main`, ki je dodal star canonical-v2/QLoRA prompt. Ta prompt je po novi
arhitekturi presežen in se ohranja samo kot zgodovinski dokument z jasno oznako
`SUPERSEDED`.

Zgodovinska arhitekturna veja je vsebovala B14 sprejemno dokumentacijo, ki
navaja:

- arhiv stare tekstovne arhitekture;
- 632 uspešnih kontroliranih testov;
- 643 uspešnih vseh takrat odkritih testov;
- 156-vrstično 12 × 13 matriko nad zamrznjenimi nativnimi bundle-i;
- delujoč deterministični end-to-end cikel;
- delujoč GUI;
- en kontroliran lokalni Ollama Racio smoke run;
- eksplicitno navedene manjkajoče integracije.

Ta dokument je bil ob integraciji ohranjen nespremenjen kot zgodovinski B14
zapis. Morebitni novi rezultati gredo v nov dodatek, ne v retroaktivno
prepisovanje B14 poročila.

---

# 2. Nespremenljivi arhitekturni invarianti

Naslednje faze ne smejo podreti že sprejetega jedra.

## 2.1 Nativni procesorji

- Racio, Emocio in Instinkt zaključijo svoj nativni proces pred governance.
- Nativni procesor ne dobi `character_profile`, authority tiera ali profile weighta.
- Isti `NativeMindBundle` je mogoče uporabiti za vseh 13 karakterjev.
- Native bundle je immutable in content-addressed.
- Noben poznejši LLM ali VLM ne sme popraviti oziroma mutirati nativnega sklepa za nazaj.

## 2.2 Racio

- Racio je edini neposredno zavestni procesor.
- `ConsciousDecision.made_by` je vedno `R`.
- Racio kot nativni razum, Racio kot interpreter in Racio kot narrator so ločene funkcije.
- Interpreter ne sme prejeti skritega Emocievega ali Instinktovega ground trutha.
- Narrator ne sme spremeniti zavestne odločitve ali vedenjskega rezultata.

## 2.3 Emocio

- Emociev sklep nastane pred Racijevo interpretacijo.
- Generated image ni objektivno dejstvo zunanjega dogodka.
- Grounded evidence, strukturirana notranja predstava in renderirana slika so tri različne plasti.
- Emocieva notranja domišljija sme vplivati na Emociev sklep samo v izrecnem `visual_cognition` načinu.
- Renderer ne sme postati prikrit odločevalec.

## 2.4 Instinkt

- Instinktov nativni sklep nastane pred verbalizacijo.
- Telesno stanje, signal intensity ali strah ne spreminjajo strukturnega karakterja.
- Vsak avtomatsko napovedan body effect mora imeti provenance in negotovost.
- Instinkt ni medicinski diagnostični model.

## 2.5 Karakter

- Karakter je ordinalen, ne numerično utežen.
- Confidence, intensity, situational keywords in stres ne spreminjajo authority tierov.
- Pri parnih značajih podrejeni razum ni samodejni tie-breaker.
- Pri `R=E=I` velja dva od treh.
- `simulated_spoznanje` zahteva enak sklep vseh treh.

## 2.6 Sprejemanje

- Sprejemanje ne pomeni nujno soglasja.
- Sprejemanje ne pomeni nujno majhnega, varnega ali reverzibilnega koraka.
- Sprejemanje vpliva na vidnost, prevod, sodelovanje, delegacijo in sabotiranje.
- Sprejemanje ne spreminja hierarhije karakterja.

## 2.7 Ego

- Ego nima glasu, vote API-ja ali `preferred_option`.
- `EgoMeasure` je en takt.
- `EgoTrace` je append-only izvedena zgodovina.
- `EgoCompositionSnapshot` je izpeljan model skladbe.
- `EgoReflector`, če bo pozneje dodan, je analitik in ne odločevalec.
- Racijeva samopodoba ni enaka Egu.

---

# 3. Pravila izvajanja za Codex

## 3.1 Ena faza, en pregled

Po vsaki fazi:

1. zaženi predpisane teste;
2. pripravi poročilo;
3. preveri, da delo še vedno poteka na `main` in da so nepovezane uporabnikove
   spremembe ostale nestageane;
4. naredi majhen commit oziroma omejeno serijo commitov neposredno na `main`;
5. pushaj odobreni fazni obseg neposredno na `origin/main`;
6. ustavi se in počakaj na pregled pred naslednjo fazo.

## 3.2 Brez prepisovanja zgodovine

Ta podrazdelek opisuje že zaključeno zgodovinsko integracijo M0–M2. Ne daje
dovoljenja za novo fazno oziroma feature vejo; za vse nadaljnje delo velja
izključno pravilo 3.3. Zgodovinski ledger beleži, da sprejeta integracija ni
uporabila rebasea, squash mergea ali force-pusha, da baseline tag in SHA-ledger
v B14 poročilu nista bila premaknjena ter da je bila integracija izvedena z
merge commitom. To so dejstva o zaključeni integraciji, ne ponovljiv workflow.

Razlog: B14, arhiv in rollback dokumentacija se sklicujejo na konkretne commite.

## 3.3 Vse nadaljnje faze neposredno na `main`

Od uporabnikovega navodila 2026-07-14 naprej se vse faze izvajajo striktno na
veji `main`:

- ne ustvarjaj ali uporabljaj faznih oziroma feature vej;
- ne preklapljaj na drugo vejo in ne odpiraj PR-ja kot nadomestila za neposreden
  `main` workflow;
- pred začetkom faze preveri `main` in `origin/main`;
- nepovezane uporabnikove lokalne spremembe ohrani nestageane;
- po pregledu faze commitaj in pushaj samo njen dogovorjeni obseg neposredno na
  `main`;
- če `main` in `origin/main` nista varno uskladljiva, se ustavi in poročaj;
  pomožne ali reševalne veje ne ustvarjaj;
- pravilo »ena faza, en pregled« ostane v veljavi tudi brez ločenih vej.

Imena drugih vej, ukazi za preklop vej ter PR/merge postopki v M0–M3 so samo
zgodovinski zapis že zaključene integracije. Ne smejo se uporabiti kot aktivno
navodilo in ne morejo razveljaviti tega `main`-only pravila.

## 3.4 Deterministični baseline ostane

Vsaka model-backed komponenta mora imeti:

- protocol;
- deterministic ali fake implementacijo;
- eksplicitni model-backed adapter;
- feature flag oziroma runtime mode;
- primerjalni eval;
- fail-closed vedenje;
- popoln provenance record.

Modelni neuspeh ne sme pokvariti arhitekturnega baselinea.

---

# 4. Faza M0 — zaključen zgodovinski pre-merge pregled

Faze M0–M2 so zaključeni zgodovinski integracijski zapis. Ukazi in PR koraki v
njih niso navodilo za ustvarjanje, preklop ali uporabo druge veje. Aktivno in
vse prihodnje delo poteka izključno neposredno na `main` po pravilu 3.3.

**Zgodovinski cilj:** ugotoviti takratno stanje lokalne in oddaljene veje brez
sprememb. Ta cilj je zaključen in ga ni dovoljeno ponovno izvajati kot vejni
workflow.

## 4.1 Zgodovinsko opravljene poizvedbe

Preflight je takrat prebral oddaljene refe in tage, status ter graf vej, SHA
`origin/main`, SHA zgodovinske arhitekturne veje, njun merge-base in primerjalni
diff-stat. Ta odstavek ohranja dokazni obseg pregleda, ne pa ukazov za ponovno
uporabo nekdanje veje.

## 4.2 Zgodovinsko preverjeni pogoji

- `origin/main` je bil preverjen glede na pričakovani `07a2640...`;
- potrjeno je bilo, da je zgodovinska arhitekturna veja vsebovala B14 poročilo;
- preverjeni so bili archive tag, nepričakovani dodatni commiti, lokalne
  necommitirane spremembe, takratni PR, GitHub Actions in datoteke manjkajočega
  main commita.

## 4.3 Izhod

Zgodovinski izhod je bilo poročilo:

```text
Docs/evals/merge_preflight_native_composition_2026-07-14.md
```

Poročilo je zajelo:

- source refs;
- branch graph;
- ahead/behind;
- potencialne konflikte;
- seznam dokumentacijskih podvajanj;
- testna navodila;
- priporočeno merge strategijo.

Takratni postopek je zahteval ustavitev ob nepojasnjenem dirty delovnem drevesu.

**Zgodovinski commit poročila:**

```text
docs(integration): record native-composition merge preflight
```

Faza je zaključena; ta zapis je samo zgodovinski.

---

# 5. Faza M1 — zaključena zgodovinska integracija

Ta faza je zaključena in integrirana v `main`. Spodnji zapis takratne rešitve
ni več aktiven in se ne ponavlja. Vse nadaljnje delo ostane na `main` ter se po
pregledu commita in pusha neposredno na `origin/main`.

## 5.1 Zgodovinsko preverjanje po integraciji

```powershell
git switch main
git status -sb
git rev-parse main
git rev-parse origin/main
```

## 5.2 Zgodovinski dokumentacijski konflikt oziroma podvajanje

`main` vsebuje:

```text
Docs/plans/REI_v3_Codex_first_execution_prompt.md
```

Zgodovinska arhitekturna veja je vsebovala nove načrte in arhivirane kopije
stare QLoRA smeri pod `plans/`.

Takrat uporabljena rešitev:

1. zgodovinskega dokumenta ne briši;
2. na vrh `Docs/plans/REI_v3_Codex_first_execution_prompt.md` dodaj:

```text
SUPERSEDED

Ta dokument pripada opuščeni canonical-v2/QLoRA smeri.
Aktivna arhitektura je REI Native Composition.
Glej:
- Docs/architecture/REI_NATIVE_COMPOSITION_ARCHITECTURE.md
- plans/REI_native_composition_architecture_upgrade_2026-07-13.md
- Docs/evals/rei_native_architecture_acceptance_2026-07-13.md
```

3. dokument ne sme več izgledati kot aktivno navodilo;
4. ne spreminjaj vsebine arhivske kopije;
5. posodobi `README.md`, `CURRENT.md` in `AGENTS.md`, če bi merge vrnil star opis baselinea.

## 5.3 Zgodovinski integracijski dodatek

Ustvarjen je bil:

```text
Docs/evals/rei_native_architecture_integration_addendum_2026-07-14.md
```

V njem so bili zapisani:

- pre-merge source SHA;
- merge commit SHA;
- kaj je prišlo iz `main`;
- kako je bil star prompt označen;
- da runtime ni bil namenoma spremenjen;
- testne rezultate;
- morebitne razlike v številu testov;
- GitHub Actions status.

## 5.4 Zgodovinski testi

Najprej:

```powershell
python -m pytest -q --basetemp output/pytest-merge-full
```

Nato kontrolirani suite:

```powershell
python -m pytest `
  tests/rei `
  tests/test_archive_boundary.py `
  tests/test_archive_integrity.py `
  tests/test_native_cutover.py `
  -q `
  --basetemp output/pytest-merge-controlled
```

Nato:

```powershell
python scripts/run_rei_native_cycle.py
python scripts/run_rei_native_profile_matrix.py
```

GUI smoke, če okolje dovoljuje:

```powershell
python -m uvicorn app.gui.server:app --host 127.0.0.1 --port 8765
```

Preveri:

- Native;
- Communication;
- Character;
- Ego;
- mobile width;
- browser console.

## 5.5 Zgodovinske omejitve

V tej fazi ne:

- spreminjaj procesorske logike;
- dodajaj modelov;
- spreminjaj fixture oracle;
- popravljaš B14 številk za nazaj;
- spreminjaš archive tag;
- uvajaš semantic lab.

## 5.6 Zgodovinska commita

Uporabljen merge commit:

```text
merge(main): reconcile documentation before native-composition integration
```

Po testih je bil po potrebi uporabljen še dokumentacijski commit:

```text
docs(integration): mark canonical-v2 prompt superseded and record merge verification
```

Faza je zaključena; ta zapis ni navodilo za nov merge ali drugo vejo.

---

# 6. Faza M2 — zaključen zgodovinski CI hardening

Ta faza je že integrirana v `main`. Spodnji opis PR-ja in merge načina ohranja
zgodovinski kontekst; ni aktiven workflow. Za naslednje faze se spremembe po
pregledu commitajo in pushajo neposredno na `main`, brez fazne ali feature veje.

**Zgodovinski cilj:** zagotoviti, da integracija ni bila odvisna samo od enega
lokalnega okolja.

## 6.1 Zgodovinski GitHub Actions hardening

V okviru zaključene faze je bil dodan:

```text
.github/workflows/rei-native-tests.yml
```

Minimalni jobi:

### `unit-and-domain`

- Python 3.11;
- install minimal requirements;
- `python -m pytest tests/rei tests/test_archive_boundary.py tests/test_archive_integrity.py tests/test_native_cutover.py -q`;
- brez Ollama;
- brez GPU;
- brez rendererja;
- brez browserja.

### `full-discovery`

- `python -m pytest -q`;
- poroča število collected testov;
- ne sme prikrito ignorirati `tests/rei`.

### `artifact-smoke`

- deterministični `run_rei_native_cycle.py`;
- deterministični `run_rei_native_profile_matrix.py`;
- shrani povzetek kot workflow artifact.

CI ne sme:

- zahtevati lokalnega modela;
- poskušati prenesti velikega image modela;
- zaganjati QLoRA;
- spreminjati committed artefaktov.

## 6.2 Zgodovinski PR zapis (ni izvedbeno navodilo)

Takrat predlagani naslov je bil:

```text
Merge native-modality REI architecture into main
```

Takratni PR body je moral vsebovati:

- arhitekturni povzetek;
- branch graph;
- B14 acceptance link;
- arhivski tag;
- testne rezultate;
- known limitations;
- rollback navodilo;
- breaking change;
- eksplicitno pojasnilo, da QLoRA ni del PR-ja.

## 6.3 Zgodovinski merge način (ni izvedbeno navodilo)

Izbran je bil GitHub način `Create a merge commit`; načina `Squash and merge`
in `Rebase and merge` nista bila uporabljena.

## 6.4 Zgodovinski pogoji pred mergem (ni izvedbeno navodilo)

Takrat so bili obvezno preverjeni:

- vsi CI jobi zeleni;
- branch ni več behind;
- GitHub kaže mergeable;
- ni nepojasnjenih binary sprememb;
- ni model weights;
- ni skrivnosti ali lokalnih poti;
- B14 rollback ostaja veljaven.

---

# 7. Faza M3 — zaključen zgodovinski post-merge sprejem na `main`

Ta faza je zaključena in integrirana. Spodnji `main`/tag zapis ohranja
zgodovinsko sled sprejema; ni navodilo za ponovno tagiranje ali nov vejni
workflow.

**Zgodovinski cilj:** zamrzniti novo aktivno razvojno osnovo.

## 7.1 Zgodovinsko preverjanje po mergeu

```powershell
git switch main
git pull --ff-only origin main
git rev-parse HEAD
python -m pytest -q --basetemp output/pytest-post-merge-main
python scripts/run_rei_native_cycle.py
python scripts/run_rei_native_profile_matrix.py
```

## 7.2 Release tag

Po uspešnem zgodovinskem preverjanju je bil ustvarjen in objavljen tag:

```powershell
git tag -a rei-v3-native-composition-v1 -m "Accepted REI native-modality and Ego-composition architecture"
git push origin rei-v3-native-composition-v1
```

Obstoječega taga stare arhitekture ne spreminjaj.

## 7.3 Release zapis

Ustvarjen je bil:

```text
Docs/releases/rei-v3-native-composition-v1.md
```

Zapis vključuje:

- main merge SHA;
- tag;
- arhivski rollback tag;
- povzetek arhitekture;
- test evidence;
- znane omejitve;
- naslednje faze C1–C6;
- opozorilo, da gre za raziskovalni simulator.

Zgodovinski commit:

```text
docs(release): mark native-composition v1 integration baseline
```

---

# 8. Faza C1 — kanonični semantični laboratorij

**Izvedba:** neposredno na `main`; odobreni fazni commit se pusha neposredno na
`origin/main`; fazna oziroma feature veja in PR workflow nista dovoljena.

**Cilj:** preiti iz testiranja arhitekturne pravilnosti v testiranje kakovosti notranjih REI-poti.

Trenutni fixtureji predvsem povedo:

```text
R izbere A
E izbere B
I izbere C
```

Naslednja raven mora povedati:

```text
zakaj je R prišel do A po Racijevi poti;
kakšno sliko je E zgradil in zakaj iz nje sledi B;
kaj I varuje in kakšna telesna trajektorija vodi do C;
kaj od tega Racio vidi;
kaj napačno interpretira;
kaj se spremeni pri sprejemanju;
kako karakter spremeni mandat, ne nativnih sklepov.
```

## 8.1 Lokacija

Ustvari:

```text
knowledge/semantic_lab_v1/
├── README.md
├── manifest.yaml
├── schemas/
│   ├── scenario_family.schema.json
│   ├── native_route.schema.json
│   ├── interpretation_variant.schema.json
│   └── longitudinal_sequence.schema.json
├── scenario_families/
├── review/
│   └── review_log.jsonl
└── source_index.jsonl
```

Generated test fixtureji:

```text
tests/fixtures/semantic_lab_v1/
```

Poročila:

```text
Docs/evals/semantic_lab_v1/
```

To ni training dataset. Ne dodajaj SFT exporta.

## 8.2 Podatkovni model

```python
class SourceLocator(BaseModel):
    source_file: str
    page: int | None
    section: str
    claim_ids: list[str]
    excerpt_summary_sl: str

class SemanticScenarioFamily(BaseModel):
    family_id: str
    title_sl: str
    purpose: str
    source_locators: list[SourceLocator]
    grounded_scene: SceneEvent
    person_world_variants: list[str]
    current_state_variants: list[str]
    acceptance_variants: list[str]
    language_variants: list[str]
    perturbation_variants: list[str]
    expected_route_ids: list[str]
    forbidden_shortcuts: list[str]
    review_status: str
```

```python
class CanonicalNativeRoute(BaseModel):
    route_id: str
    family_id: str
    mind: MindId
    evidence_ids: list[str]
    world_context_ids: list[str]
    route_tags: list[str]
    option_id: str | None
    decisive_representation: str
    short_decision_bridge_sl: str
    allowed_variants: list[str]
    forbidden_reasons: list[str]
    source_locators: list[SourceLocator]
```

```python
class CanonicalInterpretationVariant(BaseModel):
    interpretation_id: str
    family_id: str
    source_mind: Literal["E", "I"]
    visible_manifestation_ids: list[str]
    acceptance_mode: str
    expected_interpretation_class: Literal[
        "accurate",
        "partial",
        "omission",
        "rationalization",
        "minimization",
        "projection",
        "misclassification",
        "unknown",
    ]
    expected_option_id: str | None
    expected_motive_class: str
    notes_sl: str
```

## 8.3 Začetni nabor scenarijev

Pripravi najmanj 24 source-grounded familyjev.

Obvezne družine:

1. novoletna zaobljuba — Racijeva zavestna odločitev, ki je E/I ne sprejmeta;
2. Emocieva porušena želena slika in jeza;
3. Racijeva napačna razlaga Emocieve jeze;
4. klavstrofobija — Instinktov problem, ki ga besedni argument ne doseže;
5. poslušanje Instinktovega občutka namesto preusmerjanja pozornosti;
6. Malek — Instinkt delegira motorično nalogo Emociu;
7. Emocio poskuša delegacijo zamenjati za prevzem oblasti;
8. značaj kot pot, ne vedenje;
9. enako vedenje iz treh različnih poti;
10. enak procesorski motiv z različnimi zunanjimi vedenji;
11. parni karakter in konflikt dveh vodilnih razumov;
12. trinajsti značaj in 2-of-3;
13. spoznanje proti enostranski Racijevi odločitvi;
14. besede posluša Racio, E/I zaznavata druge kanale;
15. Racio interpretira sanjsko sliko po prebujenju;
16. Emocieva trenutna, želena in porušena slika;
17. Instinktova navezanost in strah pred izgubo;
18. Instinktova meja in možnost umika;
19. Instinktovo pomanjkanje in varčevanje;
20. sprejemanje ob izgubi — sodelovanje treh razumov;
21. nesprejemanje ob izgubi — obtoževanje in razpad sodelovanja;
22. razlika med Racijevim načrtom, Emocievo sliko poti in Instinktovim izločanjem nevarnosti;
23. motorični Emocio proti vizualnemu Emociu;
24. longitudinalni ponavljajoči se motiv za Ego skladbo.

Dodatni kandidati:

- čas pri R, E in I;
- humor pri E in I, ozaveščen prek R;
- privlačnost kot Emocieva slika;
- Racijev materialni interes proti Emocievemu statusnemu interesu;
- Instinktov asociativni strah, ki se zavestno napačno pripiše objektu;
- zaljubljenost kot začasna konvergenca;
- odpuščanje kot spoznanje vseh treh;
- ista zunanja previdnost, različni notranji izvori.

## 8.4 Variacije vsakega familyja

Najmanj:

```text
sl_canonical
sl_paraphrase
en_operational_gloss
keyword_trap
same_behavior_different_route
same_route_different_behavior
missing_information
contradictory_surface_cue
```

Vse variante enega familyja ostanejo skupaj. Ne mešaj jih med train/validation, ker treninga sploh ni.

## 8.5 Review workflow

Statusi:

```text
draft
source_checked
racio_reviewed
emocio_reviewed
instinkt_reviewed
communication_reviewed
canon_approved
fixture_generated
rejected
```

Primer postane `canon_approved` samo, če:

- ima vir;
- ne sklepa značaja iz vedenja;
- loči način procesiranja od rezultata;
- ne vnaša medicinske ali metafizične trditve kot runtime fakt;
- ima jasno negotovost;
- ne daje modelu expected answera v prompt.

## 8.6 Generator fixturejev

Dodaj:

```text
scripts/build_semantic_lab_fixtures.py
```

Generator:

- bere samo `canon_approved`;
- ustvarja immutable JSON fixtureje;
- vključi source hash;
- preveri option ID-je;
- ustvari manifest;
- ne kliče modelov.

## 8.7 Testi

```text
tests/semantic_lab/test_source_traceability.py
tests/semantic_lab/test_family_variant_grouping.py
tests/semantic_lab/test_no_behavior_to_character_shortcut.py
tests/semantic_lab/test_no_training_export.py
tests/semantic_lab/test_fixture_generation.py
tests/semantic_lab/test_slovenian_canonical_text_required.py
```

## 8.8 Quality gate

- najmanj 24 familyjev;
- najmanj 8 variant na family;
- 100 % source traceability;
- 0 neodobrenih fixturejev;
- 0 model-generated gold primerov;
- 0 training entrypointov;
- vsi testi uspejo.

Commit:

```text
feat(eval): add source-grounded REI semantic laboratory
```

---

# 9. Faza C2 — semantični evaluator

**Izvedba:** neposredno na `main`; odobreni fazni commit se pusha neposredno na
`origin/main`; fazna oziroma feature veja in PR workflow nista dovoljena.

**Cilj:** ocenjevati notranjo pot, ne samo pravilnost JSON-a ali prisotnost ključnih besed.

## 9.1 Nova komponenta

```text
app/backend/rei/evaluation/
├── models.py
├── native_routes.py
├── racio_eval.py
├── emocio_eval.py
├── instinkt_eval.py
├── communication_eval.py
├── ego_eval.py
├── bilingual_eval.py
├── human_review.py
└── report.py
```

## 9.2 Skupne metrike

- schema validity;
- provenance completeness;
- allowed option validity;
- source evidence coverage;
- unsupported claim count;
- profile leakage;
- hidden-ground-truth leakage;
- confidence/uncertainty calibration;
- abstention correctness;
- Slovenian terminology consistency;
- cross-language semantic consistency.

## 9.3 Racio

Ocenjuj:

- dejstvo proti neznanki;
- kronološko in vzročno urejanje;
- uporabo eksplicitnih pravil;
- ločevanje koristi od moralne ali statusne razlage;
- prepoved izmišljanja E/I motivov;
- možnost racionalizacije;
- option ID;
- kratke route tags.

Ne uporabljaj kriterija:

```text
Racio je previden
Racio vedno izbere varno
Racio vedno izbere najcenejše
```

## 9.4 Emocio

Ocenjuj:

- ali obstajajo current/desired/broken scene;
- ali je jaz pravilno umeščen v prizor;
- ali je zaznana vidnost, pripadnost, privlačnost, tekmovanje oziroma ovira, kadar to podpira primer;
- ali se želena transformacija ujema z virom;
- ali renderer-added element ni zamenjan za grounded fact;
- option rollout;
- native option;
- razliko med vizualnim in motoričnim Emociem.

## 9.5 Instinkt

Ocenjuj:

- nevarnost;
- izgubo;
- mejo;
- zaupanje;
- navezanost;
- pomanjkanje;
- možnost umika;
- telesno trajektorijo;
- protected target;
- recoverability;
- abstention ob premalo podatkih.

Ne ocenjuj ga samo po tem, ali je izbral umik.

## 9.6 Komunikacija

Ocenjuj:

- koliko manifestacije je bilo vidne;
- ali Racio sklepa znotraj vidnega;
- option inference;
- motive class;
- distortion type;
- pretirano samozavest;
- alternativne hipoteze;
- razhajanje med native signalom in conscious narrative.

Evaluator sme videti ground truth. Interpreter ga ne sme.

## 9.7 Ego

Ocenjuj:

- ali motif res temelji na več measure-ih;
- false motif rate;
- missed motif rate;
- ponavljajoče se translation gaps;
- unresolved tension continuity;
- ločitev Racio self-narrative od composition;
- pravilnost modality projections.

## 9.8 Human review

Dodaj blind review način:

- reviewer ne vidi target labela, kadar ocenjuje identiteto procesorja;
- reviewer vidi vir in grounded scene šele po prvem slepem izboru;
- oceni:
  - kateri razum;
  - katera pot;
  - kakovost sklepa;
  - kakovost prevoda;
  - stopnjo negotovosti.

Shranjuj reviewer agreement.

## 9.9 Poročila

```text
Docs/evals/semantic_lab_v1/{run_id}/
├── summary.md
├── metrics.json
├── failures.jsonl
├── confusion_matrices.json
├── bilingual_consistency.json
└── human_review_summary.md
```

## 9.10 Quality gate

Pred modelnimi integracijami mora evaluator:

- pravilno oceniti vse ročno pripravljene pozitivne in negativne fixtureje;
- zaznati profile leakage;
- zaznati hidden-ground-truth leakage;
- razlikovati accurate interpretation od rationalization fixtureja;
- ne uporabljati produkcijskih keywordov kot edini kriterij.

Commit:

```text
feat(eval): add semantic route and translation evaluation
```

---

# 10. Faza C3 — pravi RacioInterpreter

**Izvedba:** neposredno na `main`; odobreni fazni commit se pusha neposredno na
`origin/main`; fazna oziroma feature veja in PR workflow nista dovoljena.

**Cilj:** Racio naj prvič res interpretira Emocieve manifestacije in Instinktovo telesno stanje, ne da bi videl nativni ground truth.

## 10.1 Najprej uvedi ConsciousAccessFilter

Sprejemanje naj ne deluje tako, da prompt modelu naroči:

```text
zdaj napačno interpretiraj Emocia
```

Namesto tega naj vpliva na signal, ki pride v zavest.

```python
class ConsciousAccessPacket(BaseModel):
    source_mind: Literal["E", "I"]
    visible_observations: list[ManifestationObservation]
    omitted_observation_ids: list[str]
    degraded_observation_ids: list[str]
    visible_artifact_ids: list[str]
    public_option_scope: list[str]
    channel_quality: float
    uncertainty: str
```

`AcceptanceState` določa:

- visibility;
- fidelity;
- suppression;
- signal noise;
- delegation openness.

Racio vidi samo rezultat filtra.

Ground truth ostane v evaluatorju.

## 10.2 Interpreter protocol

```python
class RacioInterpreterProvider(Protocol):
    def interpret(
        self,
        packet: ConsciousAccessPacket,
        call_spec: ProviderCallSpec,
    ) -> RacioInterpretation:
        ...
```

Implementacije:

```text
DeterministicRacioInterpreter
StructuredLLMRacioInterpreter
VisionLanguageRacioInterpreter
```

## 10.3 Izhod

```python
class RacioInterpretation(BaseModel):
    source_mind: Literal["E", "I"]
    cited_observation_ids: list[str]
    inferred_option_id: str | None
    inferred_action_tendency: str
    inferred_motive_class: str
    confidence: float
    alternative_hypotheses: list[str]
    unresolved_ambiguity: str
```

Ne zahtevaj dolgega chain-of-thoughta.

## 10.4 Prva modelna stopnja

Najprej strukturirani tekstovni vhod:

- Emocio manifestation fields;
- Instinkt manifestation fields;
- brez slik;
- brez native optiona;
- brez hidden motive.

Primerjaj:

```text
deterministic baseline
vs.
local LLM interpreter
```

## 10.5 Druga stopnja

Dodaj:

- Emocieve visible image artifacts;
- Instinktov body trajectory kot graf oziroma strukturiran vizualni artefakt;
- VLM adapter;
- isti strogi JSON contract.

## 10.6 Model registry

```text
config/racio_interpreter_models.yaml
```

Vsak kandidat:

- model ID;
- revision/digest;
- runtime;
- modality support;
- Slovenian baseline;
- max context;
- hardware requirements;
- license;
- benchmark status.

Ne izberi produkcijskega modela v kodi.

## 10.7 Ablacije

Za isti primer:

```text
structured_only
image_only
structured_plus_image
body_structured_only
body_graph_plus_structured
```

Ocenjuj, kateri kanal Raciju dejansko pomaga.

## 10.8 Slovenščina

Vsak canonical primer ima:

- slovenski izvirnik;
- angleški operational gloss.

Model mora ohraniti:

- option inference;
- motive class;
- uncertainty;
- REI terminologijo.

Ne ocenjuj kakovosti samo po angleščini.

## 10.9 Varnost

Interpreter:

- ne določa značaja resnične osebe;
- ne predstavlja hipoteze kot gotovost;
- ne uporablja modela za manipulacijo;
- ne dobi metafizičnih claimov;
- ne dobi diagnostic labela.

## 10.10 Quality gate

Obvezno:

- 0 hidden native payload leakage;
- 0 character/profile leakage;
- 100 % valid JSON;
- option accuracy na nedvoumnih semantic-lab primerih boljša od deterministic baselinea;
- nizka samozavest oziroma abstention na dvoumnih primerih;
- vsaka interpretacija citira dejansko vidno observation;
- nobena interpretacija ne mutira native bundlea;
- slovenski in angleški rezultat sta semantično skladna v dogovorjeni toleranci.

Commit:

```text
feat(communication): add model-backed Racio interpretation behind conscious-access boundary
```

## 10.11 Kontrolirana remediation — 2026-07-15

C3 runtime ostaja integriran, model-quality gate pa ostaja `blocked`. Pred novim
modelnim klicem se ločen remediation protokol pregleda, commita neposredno na
`main` in pusha neposredno na `origin/main`; druga veja ali PR workflow nista
dovoljena:

- kandidat `qwen3.6:35b` je pripet z natančnim Ollama digestom samo kot
  `c3_candidate`, brez default ali production izbire;
- provider v6 ohranja isti conscious-access prompt/schema in dodaja samo
  stabilne sanitizirane failure kategorije ter hash/velikost zavrnjenega
  odziva, brez njegove vsebine;
- novi v2 holdout je create-only, model-free, ročno avtoriran, fizično loči
  public/gold in se v manifestu veže na predhodni protocol-freeze commit;
- holdout se mora izvesti prvi, stari nespremenjeni regression corpus drugi,
  oba z istim pripetim provider contractom in brez vmesnega tuninga;
- v2 gate zahteva uspeh vseh 32 primerov; pragovi ostajajo poimenovane
  implementacijske hipoteze, ne empirična psihološka trditev.

Avtoritativen protokol je:

```text
Docs/evals/semantic_lab_v1/c3_remediation_protocol_2026-07-15.md
```

Ta protokolni checkpoint sam še ne izvaja modela, ne odblokira C3/C7 in ne
odpira C9. Poznejša uradna izvedba je evidentirana v naslednjem podpoglavju.

## 10.12 Uradna paired izvedba remediation protokola — 2026-07-15

Protokol je bil zamrznjen v commitu `d74891c`, create-only holdout in paired
runner pa zapečatena v commitu `707cb20`. Nato je bil brez vmesnega tuninga
izveden uradni zaporedni par: najprej nedotaknjeni v2 holdout in zatem
nespremenjeni regression corpus. Kanonični rezultati so objavljeni v commitu
`e66f14c` pod:

```text
Docs/evals/semantic_lab_v1/c3-racio-official-pair-qwen3-6-35b-2026-07-15/
```

Izvedba je uporabila kandidata `qwen3.6:35b` z digestom
`07d35212591fc27746f0a317c975a6d68754fb38e9053d82e25f06057af28522`,
provider `rei-ollama-racio-interpreter-c3-v6`, `num_ctx=65536`,
`num_gpu=999`, `retry_count=0` in `fallback_mode=none`. Vseh 64 načrtovanih
modelnih klicev je bilo izvedenih s polnim GPU offloadom; izvajalnih napak ni
bilo.

Rezultat ni prestal quality gatea:

- untouched holdout: `23/32`, `quality_gate_pass=false`;
- frozen regression: `23/32`, `quality_gate_pass=false`;
- oba korpusa: 100 % veljaven strukturiran izhod, brez hidden/profile leakage,
  mutacije inputa, citation-scope ali provenance-scope napak;
- neuspeh je semantičen: vsak korpus ima devet neuspešnih primerov, zato strogi
  v2 pogoj `32/32` ni dosežen.

C3 produkcijski model gate in z njim povezani C7 blocker zato ostajata
`blocked`. Kandidat ni promoviran v default ali production status in ta rezultat
ne odpira C9.

---

# 11. Faza C4 — Emocio kot prava vizualna kognicija

**Izvedba:** neposredno na `main`; odobreni fazni commit se pusha neposredno na
`origin/main`; fazna oziroma feature veja in PR workflow nista dovoljena.

**Cilj:** image generator naj ne bo samo ilustrator že dokončanega sklepa, ampak nadzorovan del Emocieve notranje predstavne poti.

Sedanji `structured_only` Emocio ostane referenčni baseline.

## 11.0 Status integracije 2026-07-14

Tehnični C4 runtime je integriran neposredno v `main`. Integracija vključuje
eksplicitne cognition-mode pogodbe, provenance-closed current-first renderer,
pinned DINOv2 encoding in visual valuation, fail-closed approval/authority
mejo, integracijo v engine ter trajni cold replay konfiguracije, klicev,
opozoril, PNG-jev in vektorjev.

Celoten `tests/rei` paket je po integraciji zelen (`825 passed`). Tehnični
runtime je zato sprejet, vendar semantic-model quality gate ostaja odprt:

- FLUX.2 Klein kandidat ni prestal človeškega pregleda stabilnosti akcij;
- DINOv2 je pravilno zaznal action collapse in zavrnil visual fusion;
- repozitorijski seznam dovoljenih visual-influence authority artefaktov je
  namenoma prazen, zato produkcijski visual influence ostaja onemogočen;
- seed/style/language/renderer robustness pregled še ni zaključen.

Kanonično fazno poročilo je
[`c4_runtime_integration_acceptance_2026-07-14.md`](../Docs/evals/semantic_lab_v1/c4_runtime_integration_acceptance_2026-07-14.md).

## 11.0.1 Kontrolirana capacity remediation — 2026-07-15

Obstoječi LongCat/FireRed screen ostaja tehnično veljaven negativni dokaz, vendar
FireRedova izmerjena projekcija približno 295 GPU-ur ne dopušča tihega zagona
polne matrike. Pred novim prenosom ali modelnim klicem je zato na `main`
zapečaten ločen protokol:

```text
Docs/evals/semantic_lab_v1/c4_visual_remediation_protocol_2026-07-15.md
```

Kot nova implementation hypothesis sta v njem pripeta
`LongCat-Image-Edit-Turbo` za primarni bounded screen in neodvisni
`OmniGen-v1-diffusers` za alternate-renderer screen. Protokol zahteva zunanji
offline snapshot, popoln file manifest, process-tree hard timeout, enocelični
capacity/semantic stop pred razširitvijo, nespremenjen DINOv2 collapse prag ter
ločeno človeško review/authority sled. En sintetični 48-cell screen lahko model
zavrne, ne more pa sam zapreti širšega gatea za vse Emocio semantic-lab route.

Ta pin ne prenaša ali izvaja modela, ne podeljuje visual influence authority in
ne odblokira C4/C7/C9.

Model-free varnostni foundation za ta protokol je integriran neposredno na
`main` s commitom `303da44bf7d240dc91ae39e5ff3331ad8112fca1`. Vključuje
content-addressed slepi review z zunanjo enkratno ledger attestacijo, omejeno
preverjanje PNG bajtov, parent-owned Windows Job process-tree runner in enotne
resource-telemetry pogodbe. Commit ni izvedel nobenega modelnega klica in ne
podeljuje semantične ali produkcijske avtoritete.

Model-free Stage 1 integracija je nato integrirana neposredno na `main` s
commitoma `5c39c6abba7f70a07502b975e34d03cc16b97ee3c` in
`e04e21f00fc0322d8b64fa096a51042ee02022ed`. Dodaja exact-snapshot/provider
adapterje, izolirani stdlib bootstrap, durable background-telemetry
finalizacijo, atomski member marker ter receipt-bound DINO in display/review
porabnike. Noben model ali DINOv2 ni bil naložen ali poklican, človeški review
ni bil izveden in avtoriteta ni podeljena. Acceptance je zapisan v
[`c4_stage1_model_free_integration_acceptance_2026-07-15.md`](../Docs/evals/semantic_lab_v1/c4_stage1_model_free_integration_acceptance_2026-07-15.md).

Pred prvim modelnim klicem ostajata obvezna ločen pregled tega acceptance zapisa
in nov zunanji copy-only worker runtime brez hardlinkov ali reparse-pointov.
Foundation acceptance ostaja v
[`c4_visual_remediation_foundation_acceptance_2026-07-15.md`](../Docs/evals/semantic_lab_v1/c4_visual_remediation_foundation_acceptance_2026-07-15.md).

## 11.1 Tri runtime načini

```python
EmocioCognitionMode = Literal[
    "structured_only",
    "render_observe",
    "visual_cognition",
]
```

### `structured_only`

Sedanji model:

```text
scene specs -> structured valuation -> native conclusion
```

### `render_observe`

```text
scene specs -> renderer -> images
native conclusion še vedno iz structured valuation
```

Uporablja se za testiranje rendererja in Racijevega gledanja slik.

### `visual_cognition`

```text
grounded current scene spec
desired scene spec
broken scene spec
option rollout specs
        ↓
render / image-to-image
        ↓
image encoder / visual representation
        ↓
visual comparison
        ↓
fused Emocio valuation
        ↓
EmocioNativeConclusion
```

Samo ta način dopušča, da notranje slike vplivajo na Emociev sklep.

## 11.2 Loči tri vrste vizualnega artefakta

```python
class GroundedVisualRepresentation(BaseModel):
    source_evidence_ids: list[str]
    scene_spec_id: str
    external_fact_boundary: str

class ImaginedVisualArtifact(BaseModel):
    artifact_id: str
    originating_scene_spec_id: str
    option_id: str | None
    seed: int
    model_identity: ProviderIdentity
    internal_only: Literal[True] = True
    ungrounded_elements: list[str]

class VisualEmbeddingArtifact(BaseModel):
    source_artifact_id: str
    encoder_identity: ProviderIdentity
    vector_hash: str
    dimensions: int
```

## 11.3 Ključno epistemološko pravilo

Generated slika:

- ni dokaz o zunanjem svetu;
- ne sme dodati `SceneEvent.evidence`;
- ne sme popravljati grounded scene speca;
- je lahko legitimna Emocieva notranja predstava;
- lahko vpliva na Emocievo vrednotenje samo znotraj nativnega procesa.

To loči:

```text
halucinacija o realnosti
od
notranje domišljije
```

## 11.4 Renderer

Uporabi obstoječi provider protocol.

Dodaj realni local smoke:

- ena majhna serija;
- fiksni model revision;
- fiksni seed;
- brez avtomatskega prenosa velikih modelov v CI;
- cache po `scene_spec_hash + seed + model_revision`;
- timeout;
- fail-closed;
- no silent fallback.

## 11.5 Image-to-image rollout

Za option rollout naj bo osnovna current scene ista.

```text
current scene image
        ↓
option-specific transformation
        ↓
future scene image
```

To bolje ohrani identiteto, položaj sebe in osnovno kompozicijo kot neodvisni text-to-image prompti.

## 11.6 Image encoder

Dodaj protocol:

```python
class ImageEncoder(Protocol):
    def encode(self, artifact: ImageArtifact) -> VisualEmbeddingArtifact:
        ...
```

Prva uporaba embeddingov naj bo ozka:

- similarity current ↔ desired;
- similarity option rollout ↔ desired;
- similarity option rollout ↔ broken;
- consistency med seeds;
- ne poskušaj takoj iz embeddinga razbrati vseh socialnih lastnosti.

## 11.7 Visual valuation

```python
class VisualValuationPolicy(BaseModel):
    structured_weight: float
    desired_similarity_weight: float
    broken_avoidance_weight: float
    seed_consistency_penalty: float
    uncertainty_penalty: float
```

To so Emocieve interne implementacijske uteži, ne karakterne uteži.

Vse morajo biti v configu in označene kot `implementation_hypothesis`.

## 11.8 Visual world memory

Emociev svet naj shranjuje:

- scene spec;
- image artifact reference;
- embedding;
- desired/broken relation;
- outcome;
- social meaning;
- motor pattern.

Ne shranjuj samo Racijevega captiona.

## 11.9 Robustnost

Za vsak semantic-lab Emocio primer testiraj:

- 3 seeds;
- najmanj 2 vizualna sloga;
- slovenski in angleški prompt gloss;
- zamenjan vrstni red možnosti;
- enak scene spec z drugačnim rendererjem.

Cilj ni bit-identična slika. Cilj je stabilna Emocieva semantična smer.

## 11.10 Testi

```text
test_generated_image_never_becomes_external_evidence
test_imagined_visual_can_influence_emocio_only_in_visual_mode
test_renderer_failure_falls_back_to_structured_mode_explicitly
test_scene_identity_preserved_in_img2img_rollout
test_seed_and_model_recorded
test_option_order_does_not_change_scene_identity
test_racio_caption_cannot_mutate_emocio_native_conclusion
test_same_scene_different_emocio_world_can_change_desired_scene
test_visual_ablation_report_is_reproducible
```

## 11.11 Quality gate

- real local renderer smoke uspe;
- vsaka slika ima provenance;
- 0 grounded-evidence contamination;
- visual mode lahko spremeni Emociev sklep samo skozi dokumentiran visual valuation;
- semantic-lab review potrdi, da so current/desired/broken scene smiselne;
- seed/style variacije ne povzročajo naključnega action collapsea;
- structured baseline ostane delujoč.

**Status 2026-07-14:** tehnična runtime, provenance, replay in regression
zapora je prestana. Semantična zapora modelnega kandidata ostaja odprta, zato
ta status ne dovoljuje pinanja produkcijske visual-influence authority.

Integrirani commiti:

```text
d671796 feat(emocio): add explicit visual cognition contracts
b849008 feat(emocio): add provenance-closed visual renderer
983c691 feat(emocio): add provenance-closed visual valuation
a625200 feat(emocio): integrate provenance-closed visual cognition
2d9948d feat(emocio): close configured visual runtime replay
c304404 feat(emocio): add provenance-closed composite editor screen
```

---

# 12. Faza C5 — Instinktov samodejni body-effect mapper

**Izvedba:** neposredno na `main`; odobreni fazni commit se pusha neposredno na
`origin/main`; fazna oziroma feature veja in PR workflow nista dovoljena.

**Cilj:** odstraniti potrebo, da uporabnik ročno poda učinek vsake možnosti na telo.

## 12.1 Nova meja

```python
class EmbodiedCueInterpreter(Protocol):
    def infer_effects(
        self,
        scene: SceneEvent,
        packet: InstinktInputPacket,
        world: InstinktWorld,
        body: BodyState,
        option: DecisionOption,
    ) -> OptionBodyEffectPrediction:
        ...
```

## 12.2 Cue taxonomy

Začetne kategorije:

```text
physical_threat
pain_or_injury
uncertainty
predictability
trust
betrayal
boundary
attachment
abandonment
resource_security
scarcity
escape_availability
social_safety
protected_other
fatigue
temperature_or_environment
```

Vsaka kategorija:

- canonical source status;
- implementation mapping;
- supported evidence modalities;
- allowed body dimensions;
- uncertainty rule.

Lokacija:

```text
knowledge/canon_v2/instinkt_effect_rules.yaml
```

## 12.3 Izhod

```python
class BodyEffectEvidence(BaseModel):
    evidence_id: str
    cue_class: str
    association_ids: list[str]
    predicted_deltas: list[BodyDelta]
    confidence: float
    uncertainty: str

class OptionBodyEffectPrediction(BaseModel):
    option_id: str
    evidence: list[BodyEffectEvidence]
    combined_deltas: list[BodyDelta]
    unsupported_dimensions: list[str]
    conflict_flags: list[str]
    abstains: bool
```

## 12.4 Prva implementacija

`RuleBasedEmbodiedCueInterpreter`:

- transparentna;
- konfigurabilna;
- brez LLM;
- brez character profila;
- brez keyword-only odločitve;
- uporablja grounded evidence in Instinkt associations;
- ob premalo podatkih abstinira.

Keyword match je lahko samo prvi cue candidate. Končna delta mora imeti:

- evidence ref;
- cue class;
- association ref ali jasno default pravilo;
- uncertainty.

## 12.5 Manual override ostane

Za canonical fixtureje ohrani:

```text
manual_effect_specs
```

Način:

```python
effect_source = Literal[
    "manual_fixture",
    "rule_based",
    "model_backed",
]
```

S tem lahko primerjaš avtomatski mapper z ročnim goldom.

## 12.6 Asociativni spomin

Mapper naj poišče podobne pretekle dogodke po:

- cue signature;
- protected target;
- body-state similarity;
- loss class;
- trust/boundary context.

Rezultat association retrievala ne sme biti avtomatsko dejstvo. Je Instinktova asociativna podlaga.

## 12.7 Konfliktni cue-i

Primer:

```text
večja plača poveča resource security
selitev zmanjša attachment security
pogodba poveča predictability
neznano okolje poveča uncertainty
```

Mapper mora ohraniti večdimenzionalnost. Ne sme vsega zrušiti v en `risk_score`.

## 12.8 Outcome learning

Po dejanskem `OutcomeRecord`:

- primerjaj napovedano in doživeto;
- dodaj novo association event;
- ne spreminjaj prejšnjega zapisa;
- body/world update je nov content-addressed artefakt.

## 12.9 Model-backed naslednik

Dodaj protocol in stub, ne produkcijskega LLM odločanja.

Morebitni model-backed mapper pozneje:

- predlaga cue classes;
- ne piše končnega body statea brez validatorja;
- mora citirati evidence;
- mora prestati manual-gold eval;
- ne sme videti karakterja.

## 12.10 Testi

```text
test_rule_based_effects_have_provenance
test_unsupported_event_abstains
test_character_never_enters_body_mapper
test_same_event_different_body_state_can_change_rollout
test_same_event_different_instinkt_world_can_change_association
test_conflicting_cues_remain_multidimensional
test_manual_fixture_and_auto_mapper_can_be_compared
test_outcome_update_is_append_only
test_no_medical_diagnosis_fields
```

## 12.11 Quality gate

- avtomatski mapper pokrije vse semantic-lab Instinkt primere;
- 100 % deltas imajo provenance;
- 0 character leakage;
- 0 silent defaults;
- manual-vs-auto report obstaja;
- abstention je dovoljen in pravilno prikazan;
- obstoječi body simulator ostane nespremenjeno testiran.

Commit:

```text
feat(instinkt): infer grounded option body effects before protective rollouts
```

## 12.12 Status integracije 2026-07-15

C5 runtime, provenance, outcome-learning in deterministic replay pogodbe so
integrirane neposredno v `main`. Avtoritativen fazni izhod je:

```text
Docs/evals/semantic_lab_v1/c5-body-mapper-v3-2026-07-14/
```

Sprejeti v3 bounded-software gate beleži:

- 12 semantičnih družin in 36/36 pozitivnih celic;
- 72/72 popolnih option effect-vector ujemanj;
- 17/17 negativnih kontrol;
- provenance za 171/171 emitiranih delt;
- 0 character leakage, 0 silent defaults in 0 contract violations;
- report ID `body_mapper_evaluation_174f21e1f7c02ecbdbc08bcb428c3464`;
- gold SHA-256 `998526da3efa25adcec247cabd1b4801cbe478a311ae0e9eac4e83e425a4b6a4`.

Engine poleg tipiziranih evidence bindingov zahteva exactno materializacijo
Instinktovega association indeksa, zgodovino vodi ločeno od trenutnih cue
laneov in jo aktivira prek projection ID/hash B8 memory tokena. Post-cycle
učenje uporablja caller-presented action receipt, normalizirane meritve,
append-only body/world artefakte ter obvezni cold deterministic replay.

Ta gate je izrecno `bounded_software_contract` z oznakama
`internal_non_blind` in `implementation_hypothesis`. Ne predstavlja zunanje
slepe semantične avtoritete in ne zapira odprtega C4 modelnega quality gatea.

---

# 13. Faza C6 — longitudinalni Ego kot skladba

**Izvedba:** neposredno na `main`; odobreni fazni commit se pusha neposredno na
`origin/main`; fazna oziroma feature veja in PR workflow nista dovoljena.

**Cilj:** preveriti, ali Ego skozi zaporedje ciklov res predstavlja nastajajočo skladbo, ki povratno oblikuje svetove treh razumov.

## 13.1 Longitudinalni scenario model

```python
class LongitudinalEventStep(BaseModel):
    step_id: str
    scene: SceneEvent
    expected_outcome_mode: str
    external_outcome: OutcomeRecord | None

class LongitudinalScenario(BaseModel):
    sequence_id: str
    initial_person_state: PersonState
    steps: list[LongitudinalEventStep]
    expected_motifs: list[str]
    expected_translation_patterns: list[str]
    expected_world_changes: list[str]
```

## 13.2 Začetne sekvence

Najmanj 10 sekvenc po 10–30 ciklov:

1. Emocio išče priznanje, Racio to pripoveduje kot karierno rast;
2. Instinkt opozarja na izgubo družine, Racio signal minimizira;
3. ponavljajoče se novoletne zaobljube brez sprejemanja;
4. parni karakter z večkratnim zastojem;
5. sprejemajoča delegacija kompetentnemu podrejenemu razumu;
6. nesprejemajoče sabotiranje;
7. isti zunanji neuspeh, trije različni svetovni update-i;
8. začetno napačen Racijev prevod, ki se skozi posledice izboljša;
9. dolgoročno kopičenje Instinktovega alarma;
10. postopna konvergenca vseh treh do `simulated_spoznanje`.

## 13.3 MindWorldUpdater

Ločeni updaterji:

```text
RacioWorldUpdater
EmocioWorldUpdater
InstinktWorldUpdater
```

### Racio

Shrani:

- dejstva;
- vzročne povezave;
- čas;
- obljube;
- eksplicitne sklepe;
- lastno pripoved.

### Emocio

Shrani:

- scene;
- desired/broken motifs;
- social position;
- attraction/aversion;
- motor outcome;
- image embeddings.

### Instinkt

Shrani:

- body before/after;
- protected target;
- trust;
- boundary;
- attachment;
- loss;
- recoverability;
- association.

Updater ne sme vsem trem zapisati iste tekstovne summary vsebine.

## 13.4 Ego projections

Pred naslednjim ciklom:

```text
EgoTrace
    ↓
RacioProjection
EmocioProjection
InstinktProjection
```

Vsaka projekcija mora:

- citirati measure IDs;
- vsebovati samo modalno relevantne podatke;
- ohraniti negotovost;
- ne spreminjati karakterja;
- ne postati četrto navodilo.

## 13.5 Motif engine v treh stopnjah

### Stopnja 1 — structured tags

Obstoječi exact token baseline.

### Stopnja 2 — canonical motif normalization

Slovar semantično sorodnih oznak:

```text
career_growth
professional_advancement
being_seen_as_successful
```

lahko pripadajo širšemu motivu, vendar samo ob source-grounded pravilih.

### Stopnja 3 — embedding-assisted hypothesis

Opcijski:

- clustering;
- predlog motiva;
- evidence measure IDs;
- človek ali validator potrdi;
- nikoli samodejno ne postane kanonična resnica.

## 13.6 RacioSelfNarrative proti kompoziciji

Za vsak snapshot izračunaj:

```text
claimed motive
observed recurring motive
acknowledged minds
omitted minds
recurrent translation gaps
narrative-composition divergence
```

To je diagnostični model simulatorja, ne diagnoza človeka.

## 13.7 EgoReflector

V tej fazi samo opcijski eksperiment.

Omejitve:

- read-only;
- ne sodeluje v trenutnem ciklu;
- ne piše v `GovernanceMandate`;
- ne piše neposredno v MindWorld;
- vsaka trditev citira measure IDs;
- output je `ReflectionHypothesis`;
- brez glasu »jaz, Ego«.

## 13.8 Testi

```text
test_longitudinal_trace_is_append_only
test_world_updates_are_modality_specific
test_projection_cites_measure_ids
test_same_character_different_history_changes_native_conclusions
test_character_stays_constant_across_sequence
test_racio_narrative_can_diverge_from_composition
test_structured_motif_precision
test_false_motif_is_rejected
test_embedding_hypothesis_needs_validation
test_ego_reflector_cannot_mutate_runtime
test_spoznanje_closes_previous_tension_without_rewriting_history
```

## 13.9 Quality gate

- 10 longitudinalnih sekvenc;
- vsaka najmanj 10 ciklov;
- append-only verifikacija;
- world updates so različni po modalnosti;
- naslednji native bundle dejansko uporablja preteklo projekcijo;
- motif precision na gold sekvencah doseže dogovorjeni prag;
- Racio narrative divergence je vidna;
- Ego nima decision API-ja.

Commit:

```text
feat(ego): validate longitudinal composition and modality-specific world learning
```

## 13.10 Implementacijski izid (2026-07-15)

C6 je implementiran neposredno na `main` in njegov deterministični tehnični
gate je uspešen:

- 10 poimenovanih sekvenc in 100 ciklov;
- append-only EgoTrace, konstanten Character ter measure-sourced projekcije;
- 90/90 naslednjih ciklov porabi zgodovinske bundle in popolne Emocio/Instinkt
  sidecar projekcije;
- byte-backed PNG + float32 Emocio signali so preverjeni prek kanoničnih
  create-only storage receiptov;
- Emocio socialni položaj se shrani samo kot exact `social_position:*` zapis
  iz strukturiranih `current_scene` polj `self_position`, `group_belonging` in
  `status_relations`, nikoli kot sklep iz embeddinga;
- predicted Instinkt recoverability ostane epistemološko označen signal in se
  ne promovira v `trusted_patterns`;
- Instinkt `body_before`/`predicted_body_after`, `predicted_loss`,
  `trust_outcome`, recoverability in association-match lineage so shranjeni
  samo kot exact prediction sidecar; mutacije `associations`,
  `trusted_patterns` in `unresolved_losses` ostajajo odprte do verificiranega
  C5 outcome replaya;
- measured Instinkt/C5 replay closure ostaja fail-closed in ima coverage `0`;
- motif gate je samo stage-1 structured-tag gate; natural-language in širša
  semantična avtoriteta nista podeljeni;
- RacioSelfNarrative divergence je ločena od Ego kompozicije;
- isti trenutni prizor z zgodovino in brez nje spremeni omejene nativne
  semantične izhode, paired Character kontrola pa ohrani pred-governance native
  packet/execution/bundle invarianco;
- checked-in report je dvakrat neodvisno reproduciran in nato potrjen z
  `scripts/run_rei_longitudinal_eval.py --check`.

Avtoritetna meja reporta je strojno berljiva:

```text
gate_kind=bounded_software_contract
review_status=internal_non_blind
gold_status=implementation_hypothesis
semantic_authority_granted=false
visual_signal_scope=post_cycle_internal_evaluation_not_source_cycle_processing
measured_body_outcome_status=open_no_verified_c5_replay
instinkt_learning_scope=prediction_sidecar_only_world_mutation_open_until_verified_c5_replay
```

Artefakta sta v:

```text
Docs/evals/semantic_lab_v1/c6-longitudinal-2026-07-14/
```

Avtoritativen report ID je
`longitudinal_evaluation_28c866c199bad1e7790a57fbe4f27d9f`. Dve ločeni
reprodukciji in checked-in artefakta imajo enake SHA-256:

```text
longitudinal_evaluation.json  b6ff3c5abee578661a638621ddb6b6299d5159e5dc1668ac844b784ddc7b2fdf
dimensions.md                 a26342a87f4a86fff00bf59ed4da8afe382e91e5490a498b59641313e36d89ff
```

---

# 14. Faza C7 — integrirani semantični benchmark

**Izvedba:** neposredno na `main`; odobreni fazni commit se pusha neposredno na
`origin/main`; fazna oziroma feature veja in PR workflow nista dovoljena.

**Cilj:** preveriti celoten sistem po tem, ko so RacioInterpreter, Emocio visual cognition, Instinkt mapper in longitudinalni Ego na voljo.

## 14.1 Dva benchmark načina

### Controlled profile benchmark

- en `SceneEvent`;
- en frozen native bundle;
- vseh 13 karakterjev;
- brez ponovnega izvajanja procesorjev;
- meri samo governance in downstream razhajanja.

### Person longitudinal benchmark

- isti začetni svet;
- različni karakterji;
- skozi več ciklov nastanejo različne odločitve;
- svetovi se začnejo razlikovati;
- poznejši native sklepi so lahko različni.

To razliko mora report jasno prikazati.

## 14.2 Ablacije

Obvezno:

```text
Racio deterministic vs model-backed
Emocio structured_only vs render_observe vs visual_cognition
Instinkt manual effects vs auto mapper
Interpreter structured-only vs VLM
Ego structured motif vs semantic motif hypothesis
Acceptance accepting vs mixed vs conflicted
```

## 14.3 Meritve

- processor route identity;
- source grounding;
- option choice;
- abstention;
- translation fidelity;
- character causality;
- conscious/behavior divergence;
- spoznanje;
- cross-language consistency;
- visual robustness;
- body mapper agreement;
- longitudinal motif precision;
- latency;
- VRAM/RAM;
- artifact size;
- failure mode.

## 14.4 Brez enega agregatnega »REI scorea«

Poročilo mora ohraniti dimenzije ločeno.

Prepovedano:

```text
Model A ima REI score 87, zato je boljši.
```

Dovoljeno:

```text
Model A bolje ohranja Racijevo fact/unknown mejo.
Model B bolje interpretira Emocieve slike.
Model C ima slabšo slovensko terminologijo.
```

## 14.5 Quality gate

Sistem je pripravljen za naslednjo raziskovalno fazo, ko:

- ni arhitekturnih invariant failures;
- model-backed komponente presegajo deterministic baseline na svoji ciljni semantični nalogi;
- nobena izboljšava ne povzroči hidden-ground-truth leakage;
- slovenski rezultati niso izrazito slabši od angleških;
- visual mode ne kontaminira external evidence;
- body mapper ne skriva unsupported sklepov;
- longitudinalni Ego pokaže vsaj nekaj source-grounded ponavljajočih se motivov;
- failures so reproducibilni in shranjeni.

Commit:

```text
feat(eval): add integrated semantic and longitudinal REI benchmark
```

## 14.6 Status integracije 2026-07-15

C7 je implementiran kot determinističen, model-free integrirani benchmark.
Tehnični contract gate je uspešen, raziskovalna kakovost pa ostaja izrecno
`blocked`; semantična in produkcijska avtoriteta nista podeljeni.

Checked-in report je v:

```text
Docs/evals/semantic_lab_v1/c7-integrated-2026-07-15/
```

Avtoritativen report ID in hash sta:

```text
c7_integrated_benchmark_57c1db13906284edd641ac7cfbc6f5dc
fb96308989974776e29fbe8c7e1e185211f77155d4726a453e1158b5a3c16adc
```

Controlled benchmark ohrani isti frozen native bundle in governance za
`12 x 13 x 3 = 468` vrstic, `156` paired invariantov in nič ponovnih native
procesorskih izvajanj. Person-causality rezina ima `4/4` uspešne bounded
simulator primere; hash in izvajanje uporabljata iste corpus bajte, Character
pa ni vhod v simulator prehod.

Poročilo ohrani vseh šest ablation družin in 17 meritev ločeno. Trenutni run
ima nič modelskih klicev; 32 C3 klicev je označenih samo kot historical
evidence. Dispozicija meritev je `7 passed`, `6 blocked`, `3 observed` in
`1 not_measured`; agregatni REI score in interaction score nista uvedena.

Raziskovalni blockerji ostajajo:

```text
c3_model_quality_gate_failed
c4_semantic_visual_gate_open
vlm_interpreter_arm_not_executed
semantic_motif_arm_not_executed
uniform_resource_telemetry_missing
```

`--require-research-ready` zato reproducibilno vrne exit code `2`, medtem ko
navaden create/check tehničnega poročila uspe. C8 mora te ločene statuse
prikazati brez njihovega pretvarjanja v en sam rezultat.

---

# 15. Faza C8 — GUI semantičnega laboratorija

**Izvedba:** neposredno na `main`; odobreni fazni commit se pusha neposredno na
`origin/main`; fazna oziroma feature veja in PR workflow nista dovoljena.

**Cilj:** omogočiti človeku, da pregleda razliko med nativnim sklepom, manifestacijo, Racijevim prevodom in časovno Ego kompozicijo.

## 15.1 Semantic Lab panel

- source;
- grounded scene;
- variant;
- expected route;
- dejanski route;
- reviewer status;
- failure tags;
- slovenski/angleški side-by-side.

## 15.2 Racio Interpretation panel

Levo:

- kar je Racio dejansko videl.

Desno v debug načinu:

- nativni ground truth;
- TranslationGap;
- evaluatorjeva oznaka.

Jasno opozorilo:

```text
Racio ground trutha ni prejel.
```

## 15.3 Emocio panel

- scene specs;
- current/desired/broken;
- option rollouts;
- generated images;
- embeddings/similarity;
- structured vs visual valuation;
- native option;
- renderer-added ungrounded elements.

## 15.4 Instinkt panel

- body before;
- cue evidence;
- predicted body effects;
- association matches;
- option trajectories;
- body after;
- dominant alarm;
- abstention/uncertainty.

## 15.5 Ego timeline

- measures;
- decisions;
- outcomes;
- recurring motifs;
- translation errors;
- unresolved tensions;
- spoznanja;
- Racio self-narrative;
- R/E/I projections.

## 15.6 Varnost

- loopback only privzeto;
- brez Character diagnosis gumba;
- brez avtomatskega training exporta;
- brez skritih model callov;
- debug ground truth samo z izrecnim lokalnim stikalom.

## 15.7 Status integracije 2026-07-15

C8 je integriran in sprejemno preverjen s tem faznim commitom neposredno na
`main` na osnovi `1d8c391bb8e60f02e0f7552463069c257699b9fc`. Fazni commit
vsebuje ta statusni zapis in fazno poročilo, zato samoreferenčni končni SHA v
njiju ni vpisan.

GUI vsebuje šest ločenih pregledov: Semantic Lab, Racio, Emocio, Instinkt,
Character in Ego. Semantic Lab bere zamrznjeni C1/C2/C7 corpus in poročila skozi
integritetno preverjeno, read-only projekcijo. Neizvedene variante ostanejo
označeni kot `not_executed`; GUI ne izmišljuje dejanskega routea. C7 tehnični
`pass` in raziskovalni `blocked` sta prikazana ločeno brez agregatnega REI
rezultata.

Normalni Racio pogled vsebuje samo dejansko vidni input. Nativni ground truth,
`TranslationGap` in evaluatorjeva oznaka se pojavijo samo po izrecnem lokalnem
debug stikalu, ob izklopu pa se takoj odstranijo iz odjemalčevega stanja. Emocio,
Instinkt in Ego pogledi ohranijo zahtevane procesne meje, negotovost in
longitudinalno sled; Character ostane governance pregled in ne diagnoza.

Runtime je privzeto omejen na loopback. Host, Origin, vsebinski tip in
cross-site zahteve se preverjajo fail-closed; API odgovori imajo omejevalne
varnostne glave. Izvajanje cikla in gradnja Semantic Lab projekcije sta
konkurenčno omejena. GUI ne izvaja skritih modelskih klicev, ne omogoča
samodejnega training exporta in ne uvaja Character diagnosis gumba.

Longitudinalno zgodovino razrešuje strežnik iz polno preverjenih finalnih ali
prepared manifestov; odjemalec zgodovinskih bundle-ov ne sme injicirati.
Run artefakti so particionirani po SHA-256 namespaceu iz `ego_id`; recovery v
eni Ego particiji absolutno pregleda največ 64 vnosov, GUI Ego seja pa je
omejena na 30 measures. Nativni bundle nad 2 MiB se zavrne pred persistenco.
Preverjene slike so dosegljive samo skozi Ego-particionirano pot
`/api/ego-runs/{partition_id}/{run_id}/images/{image_id}`; URL vsebuje samo
kanonični 64-hex partition digest in nikoli surovega `ego_id`. Read-only image
lookup uporablja `FileArtifactStore(create=False)`, zato manjkajoča particija
ne ustvari direktorija ali drugega stanja. Oddaljeni opt-in ostaja
neavtenticiran trusted-single-user način; `ego_id` je namespace, ne credential,
zato izpostavitev nezaupanja vrednemu ali večuporabniškemu omrežju brez zunanje
avtentikacije ni podprta.

Avtoritativno fazno poročilo je:

```text
Docs/evals/semantic_lab_v1/c8-gui-2026-07-15/acceptance.md
```

C8 podeljuje tehnično GUI sprejemljivost, ne pa C7 raziskovalne, semantične ali
produkcijske avtoritete. Naslednji korak zato ni C9, temveč kontrolirana
image/model remediation odprtih C3/C4/C7 blockerjev.

Commit:

```text
feat(gui): add semantic native-process and longitudinal Ego workbench
```

---

# 16. Faza C9 — naslednji release

**Izvedba po izrecni odobritvi:** neposredno na `main`; release commit in
morebitni spremljevalni dokumentacijski commiti se pushajo neposredno na
`origin/main`. Tudi za C9 se ne ustvari fazna oziroma feature veja in se ne
uporabi PR workflow.

Ko so C1–C8 sprejeti:

C8 tehnični sprejem sam po sebi ne odpre C9. Pred releaseom mora biti C7
research-quality gate dejansko odblokiran z nadzorovano modelno evidenco;
trenutnih pet blockerjev se ne sme preimenovati v sprejem ali skriti v release
opombi.

```text
rei-v3-semantic-native-v1
```

Pripravi:

```text
Docs/releases/rei-v3-semantic-native-v1.md
Docs/evals/rei_semantic_native_acceptance_{date}.md
```

V poročilu loči:

- arhitekturno sprejemljivost;
- semantično kakovost;
- model-backed rezultate;
- slovenski jezik;
- znane omejitve;
- odprta vprašanja;
- kaj še ni empirično potrjeno.

Šele po tem releaseu se znova odpre razprava o QLoRA oziroma učenju.

---

# 17. Kaj Codex izrecno ne sme narediti

1. Ne squashaj arhitekturnih commitov.
2. Ne prepisuj B14 zgodovine.
3. Ne spreminjaj baseline taga.
4. Ne pošiljaj karakterja nativnim procesorjem.
5. Ne vrni decimalnih karakternih uteži v governance.
6. Ne pusti LLM-ju razreševati parnega konflikta.
7. Ne pusti Raciju videti hidden native ground trutha.
8. Ne dovoli rendererju dodajati external evidence.
9. Ne enači slike z Emociem; slika je njegov artefakt.
10. Ne enači body statea z Instinktom; telo je del njegovega procesa.
11. Ne enači agreementa s sprejemanjem.
12. Ne enači conscious decisiona z governance mandateom.
13. Ne enači behavior resultanta z zavestno odločitvijo.
14. Ne naredi Ega za agenta.
15. Ne uvajaj `EgoVote`, `EgoPreferredOption` ali `EgoDecision`.
16. Ne generiraj trening datasetov.
17. Ne uvajaj QLoRA ali LoRA.
18. Ne izbiraj končnega modela brez semantičnega benchmarka.
19. Ne uporabljaj modelnega judgea kot edinega vira resnice.
20. Ne ocenjuj karakterja resničnih ljudi.
21. Ne izvajaj medicinskih ali terapevtskih sklepov.
22. Ne uvajaj metafizičnega `LifeAgent`.
23. Ne skrivaj odprte hipoteze v fallbacku.
24. Ne prilagajaj gold primerov zato, da trenutni model zmaga.
25. Ne spremeni semantic lab v prompt-specific benchmark.

---

# 18. Predlagani commit in `main` pregled

Vse še odprte vrstice v tej tabeli pomenijo neposreden commit na `main` in push
na `origin/main`, nikoli dela na ločeni veji.

| Faza | Izvedba | Predlagani commit |
|---|---|---|
| M0 | main (integrirano) | `docs(integration): record native-composition merge preflight` |
| M1 | main (integrirano) | `merge(main): reconcile documentation before native-composition integration` |
| M1 docs | main (integrirano) | `docs(integration): mark canonical-v2 prompt superseded and record merge verification` |
| M2 | main (integrirano) | `ci: verify native REI architecture without model dependencies` |
| M3 | main (integrirano) | `docs(release): mark native-composition v1 integration baseline` |
| C1 | main (integrirano) | `feat(eval): add source-grounded REI semantic laboratory` |
| C2 | main (integrirano) | `feat(eval): add semantic route and translation evaluation` |
| C3 | main (runtime integriran; model gate blokiran) | `feat(communication): add model-backed Racio interpretation behind conscious-access boundary` |
| C4 | main (tehnični runtime integriran; semantic gate odprt) | `d671796` … `c304404` — provenance-closed visual cognition, replay in composite editor |
| C5 | main (integrirano; bounded software gate sprejet) | `feat(instinkt): infer grounded option body effects before protective rollouts` |
| C6 | main (integrirano; bounded gate uspešen; semantic authority ni podeljena) | `feat(ego): validate longitudinal composition and modality-specific world learning` |
| C7 | main (integrirano; tehnični gate uspešen, research gate blokiran) | `feat(eval): add integrated semantic and longitudinal REI benchmark` |
| C8 | main (integrirano s faznim commitom, ki vsebuje ta status) | `feat(gui): add semantic native-process and longitudinal Ego workbench` |
| C4 remediation foundation | main (integrirano; model-free, brez authority) | `303da44` — blind review, hard process-tree cancellation and resource telemetry |
| C4 remediation Stage 1 | main (integrirano; model-free, brez authority) | `5c39c6a` + `e04e21f` — exact providers, secure runner, atomic publication and receipt-bound consumers |
| C9 | main-only (še ni odprto; čaka research remediation) | `docs(release): record semantic-native v1 acceptance` |

---

# 19. Obvezni format poročila po fazi

```text
Phase:
Branch: main
Base main SHA:
Head SHA:
Changed files:
New files:
Deleted files:
Architecture changes:
Runtime changes:
Canon claims added:
Implementation hypotheses added:
Open questions added:
Tests run:
Tests passed:
Tests failed:
Model-backed runs:
Artifacts created:
Known limitations:
Regression risk:
Rollback path:
Proposed commit:
Recommended next phase:
```

Če se uvede nova operacionalizacija, jo zapiši v:

```text
knowledge/canon_v2/open_questions.md
```

z oznako:

```text
implementation_hypothesis
```

---

# 20. Trenutno neposredno navodilo Codexu

Faze M0–M3, C1, C2 in C5 so zaključene ter integrirane v `main`. C3 runtime je
integriran; uradna paired izvedba kandidata `qwen3.6:35b` je zaključena z
rezultatoma `23/32` na holdoutu in `23/32` na regression corpusu, zato njegov
produkcijski model gate ostaja blokiran. C4 tehnični
runtime in composite editor sta integrirana, semantic-model quality gate pa
ostaja odprt. C6 je integriran neposredno na `main`; njegov reproducibilni
bounded-software gate je uspešen, semantična avtoriteta pa izrecno ni podeljena.
C7 je integriran neposredno na `main`; njegov model-free tehnični contract gate
je uspešen, research-quality gate pa zaradi petih eksplicitnih blockerjev ostaja
`blocked`. C8 je integriran s tem faznim commitom neposredno na `main`; phase
commit vsebuje tudi statusni zapis in fazno poročilo. C8 ne spreminja C7
raziskovalnega statusa in ne podeljuje semantične ali produkcijske avtoritete.

C4 remediation safety foundation je integriran neposredno na `main` s commitom
`303da44bf7d240dc91ae39e5ff3331ad8112fca1`. Je model-free in ne dovoljuje
inference, avtoritativnega človeškega reviewa ali visual influence authority.
Model-free Stage 1 integracija exact providerjev, durable background
telemetrije, atomske publikacije in receipt-bound porabnikov je zaključena ter
pushana neposredno na `main` s commitoma `5c39c6a` in `e04e21f`. Prvi modelni
klic še ni bil izveden. Naslednja odobritvena točka je ločen pregled Stage 1
acceptance zapisa in priprava copy-only zunanjega worker runtimea; šele nato je
dovoljen ločen, vnaprej omejen model-backed screen.

Naslednja odobritvena točka ni C9. Najprej izvedi kontrolirano image/model
remediation odprtih C3/C4/C7 blockerjev z vnaprej pripetimi modelnimi revizijami,
nespremenjenimi determinističnimi baseline-i, popolnim provenanceom in ločenimi
quality gatei. C9 se lahko začne šele, ko raziskovalni blockerji niso več
`blocked` in je ta sprememba podprta z reproducibilnimi artefakti.

Za vsako nadaljnjo fazo velja:

```text
Preberi ta načrt in repozitorijski AGENTS.md.
Delaj neposredno na main; ne ustvarjaj, uporabljaj, objavljaj ali checkoutaj druge veje.
Pred spremembami preveri, da sta main in origin/main usklajena.
Ohrani nepovezane uporabnikove lokalne spremembe nestageane.
Izvedi samo trenutno odobreno fazo.
Zaženi predpisane teste in pripravi fazno poročilo.
Commitaj in pushaj dogovorjeni obseg neposredno na main.
Po fazi se ustavi za pregled.
Ne rebasaj, ne force-pushaj in ne premikaj baseline tagov.
```

---

# 21. Končni cilj tega načrta

Po tej seriji faz mora projekt znati pokazati ne samo:

```text
arhitektura je pravilno razdeljena
```

temveč tudi:

```text
Racio je do sklepa prišel po jezikovno-analitični poti.
Emocio je zgradil in ovrednotil notranje prizore.
Instinkt je dogodek preslikal v telesne, zaščitne posledice.
Racio je manifestaciji pravilno ali napačno interpretiral.
Karakter je določil oblast, ne pa vsebine procesorjev.
Zavestna odločitev, mandat in vedenje so ostali ločeni.
Ego je skozi več ciklov razvil prepoznavno skladbo.
```

To je naslednja prava stopnja projekta.
