# REI-v3 — načrt arhiviranja stare arhitekture in prehoda na novo multimodalno kompozicijsko arhitekturo

**Namen:** neposredno izvedbeno navodilo za Codex  
**Repozitorij:** `kotlet13/rei-v3`  
**Pregledani HEAD:** `07a26401e0b2707a79018efc2fdd7194d3062566`  
**Datum načrta:** 2026-07-13  
**Status:** ta dokument nadomešča prejšnjo smer »canonical-v2 + QLoRA«. QLoRA, fine-tuning in izbor končnih modelov so do nadaljnjega izven obsega.

---

# 0. Najpomembnejše navodilo Codexu

To ni običajen refactor. Gre za zamenjavo temeljnega računalniškega modela REI.

Izvedba mora potekati v dveh strogo ločenih delih:

1. **najprej arhiviraj trenutno delujočo tekstovno arhitekturo in dokaži, da je arhiv celovit;**
2. **šele v naslednjih commitih začni graditi novo arhitekturo.**

V istem commitu nikoli ne mešaj arhiviranja in nove implementacije.

Po vsaki fazi:

- zaženi vse predpisane teste;
- zapiši dejansko stanje in odprta vprašanja;
- pripravi majhen, razumljiv commit;
- ne skrivaj neuspelih testov;
- ne prilagajaj teorije samo zato, da bi test šel skozi;
- ne uvajaj QLoRA, LoRA, SFT ali training kode;
- ne spreminjaj izvornih dokumentov;
- ne razglašaj projektnih izpeljav za Erosove trditve.

Pred začetkom preveri:

```powershell
git status --short
git rev-parse HEAD
```

Pričakovani izhodiščni commit je:

```text
07a26401e0b2707a79018efc2fdd7194d3062566
```

Če je HEAD novejši, najprej preglej razliko in v arhivskem manifestu uporabi dejanski SHA. Ne resetiraj ali prepisuj uporabnikovih sprememb.

---

# 1. Zakaj je potreben čist arhitekturni rez

Trenutna aktivna arhitektura je zgrajena okoli:

- treh tekstovnih LLM procesorjev;
- enakega besedilnega vhoda za Racio, Emocio in Instinkt;
- decimalnih profilnih uteži;
- situacijskega bonusa, ki lahko spremeni rezultantnega vodjo;
- keyword ocenjevanja sprejemanja;
- ločenega `EgoResultant` LLM-klica;
- 156-primerovne profilne matrike;
- tekstovnega dataset workbencha.

Ta sistem je uporaben kot razvojna zgodovina in primer, kaj je bilo že preizkušeno. Ni pa več primerna osnova za novo smer, ker temeljne modalnosti vseh treh razumov še vedno simulira z istim tipom modela.

Nova arhitektura mora upoštevati naslednjo delitev:

```text
Racio    = simbolno-jezikovno, številčno, zaporedno in zavestno procesiranje
Emocio   = vizualno-prizorno, mozaično, primerjalno in motorično procesiranje
Instinkt = telesno, interoceptivno, asociativno, zaščitno in homeostatsko procesiranje
```

Poleg tega:

```text
karakter = stabilna ordinalna razporeditev oblasti med R, E in I
sprejemanje = kakovost sodelovanja in medsebojnega prevajanja
resultanta = rezultat enega cikla
Ego = skladba oziroma časovni vzorec, ki ga trije razumi skupaj ustvarjajo skozi življenje
```

Ego zato ne sme biti četrti agent, četrti glas ali četrti odločevalec.

---

# 2. Kanonične arhitekturne odločitve

Spodnje točke so za novo implementacijo obvezne. Codex jih ne sme samovoljno reinterpretirati.

## 2.1 Trije razumi so avtonomni procesorji

Vsak razum:

- prejme sebi primerno predstavitev dogodka;
- uporablja svoj svet in svoj spomin;
- po svoji poti pride do lastnega sklepa;
- lahko pride do istega zunanjega predloga kot druga dva, vendar iz drugega razloga;
- ne sme vedeti, kateri položaj ima v karakterju, kadar izvajamo kontrolirano profilno simulacijo.

## 2.2 Racio je edini neposredno zavestni razum

Nova arhitektura mora ločiti tri Racijeve funkcije:

```text
RacioNativeProcessor
RacioInterpreter
RacioCommitter / RacioNarrator
```

- `RacioNativeProcessor` je eden od treh avtonomnih razumov.
- `RacioInterpreter` poskuša zavestno razumeti Emocieve manifestacije in Instinktovo telesno stanje.
- `RacioCommitter` oblikuje zavedno odločitev.
- `RacioNarrator` oblikuje zavestno razlago odločitve in sebe.

Vsi objekti tipa `ConsciousDecision` morajo imeti:

```python
made_by = "R"
```

To ne pomeni, da je bil izvor sklepa vedno Racio.

## 2.3 Emocio mora sprejeti svoj sklep pred Racijevo interpretacijo

Prepovedan tok:

```text
slika -> Racio jo opiše -> iz Racijevega opisa določimo, kaj hoče Emocio
```

Obvezni tok:

```text
Emociev vizualni proces
    -> Emociev nativni sklep
    -> zamrznitev sklepa in artefaktov
    -> Emocieva manifestacija
    -> Racijeva interpretacija
```

Racio lahko Emocia:

- pravilno razume;
- delno razume;
- napačno prevede;
- racionalizira;
- prezre.

Nikoli pa ne sme za nazaj ustvariti Emocievega sklepa.

## 2.4 Instinkt mora sprejeti svoj sklep pred verbalizacijo

Instinktov primarni izhod ni odstavek besedila.

Njegov nativni izhod je kombinacija:

- telesnega stanja;
- sprememb telesnega stanja;
- nevarnosti;
- izgub;
- meja;
- zaupanja;
- navezanosti;
- pomanjkanja;
- možnosti umika;
- zaščitne akcijske težnje.

Besedni stavek o strahu ali nevarnosti je vedno:

```text
RacioInterpretationOfInstinkt
```

in ne Instinktov dobesedni notranji govor.

## 2.5 Karakter je stabilna ordinalna oblast

Nova koda ne uporablja decimalnih uteži za odločanje.

Karakter predstavlja:

```python
authority_tiers: list[list[MindId]]
```

Primeri:

```python
R>(E=I)  -> [["R"], ["E", "I"]]
R>E>I    -> [["R"], ["E"], ["I"]]
(R=E)>I  -> [["R", "E"], ["I"]]
R=E=I    -> [["R", "E", "I"]]
```

Intenzivnost, confidence, razpoloženje, stres ali keywordi ne smejo spremeniti `structural_character`.

Fizična oziroma funkcionalna okvara se modelira ločeno kot:

```text
ProcessorAvailability
FunctionalOverride
```

Strukturni karakter ostane zapisan tudi takrat, ko eden od procesorjev ne deluje.

## 2.6 Značaj ni celotna oseba

Osebo sestavljajo vsaj:

```text
CharacterAuthority
MindDevelopment
MindWorlds
AcceptanceState
CurrentState
EgoComposition
```

Dva človeka z istim značajem lahko sprejmeta različne odločitve, ker imajo njuni razumi različne svetove, spomine, razvitost in odnose.

## 2.7 Sprejemanje ni soglasje in ni varna majhna odločitev

Sprejemanje določa:

- ali se razumi poslušajo;
- koliko dopuščajo drugačen sklep;
- kako zvesto Racio prevaja E in I;
- ali lahko prepuščajo naloge;
- ali pride do sabotiranja;
- ali se konflikt prenaša naprej.

Sprejemanje ne določa:

- položaja v karakterju;
- tega, kateri cilj je »pravilen«;
- tega, da mora biti korak majhen, varen ali reverzibilen;
- tega, da morajo vsi trije izbrati isto.

## 2.8 Spoznanje je ločeno stanje

`Spoznanje` nastane, kadar vsi trije po svojih različnih poteh pridejo do istega sklepa.

V kodi uporabljaj:

```text
simulated_spoznanje
```

ker simulator ne dokazuje objektivne resnice, temveč notranjo konvergenco treh modeliranih procesorjev.

## 2.9 Ego ni agent

Prepovedani API-ji:

```text
EgoAgent.decide()
EgoVote
EgoPreferredOption
EgoLeadingMind
EgoDecisionMaker
```

Dovoljeni koncepti:

```text
EgoMeasure
EgoTrace
EgoCompositionSnapshot
EgoProjection
EgoReflector
RacioSelfNarrative
```

Ego je časovni vzorec skupnega delovanja. `EgoTrace` in `EgoCompositionSnapshot` sta računalniška modela tega vzorca, ne četrti razum.

---

# 3. Del A — arhiviranje trenutne arhitekture

## 3.1 Ustvari delovno vejo in oznako baselinea

Predlagana veja:

```powershell
git switch -c architecture/rei-native-composition
```

Predlagan anotiran tag:

```powershell
git tag -a rei-v3-text-llm-baseline-2026-07-13 -m "REI-v3 textual three-LLM and EgoResultant baseline before native-modalities rewrite"
```

Če Codex v okolju ne sme ustvarjati tagov, naj to jasno zapiše v poročilo in pripravi natančen ukaz za uporabnika.

Tag naj kaže na dejanski izhodiščni commit.

## 3.2 Pred arhiviranjem zaženi baseline verifikacijo

Obvezno:

```powershell
python -m pytest -q
```

Če je Ollama dosegljiv:

```powershell
python scripts\run_rei_profile_matrix.py --provider deterministic
```

in en majhen LLM smoke run, če skripta omogoča filter ali omejitev.

Ne zaganjaj novega dragega 156-case LLM runa brez izrecne potrditve.

Rezultate zapiši v:

```text
archive/rei_v3_text_llm_baseline_2026-07-13/BASELINE_VERIFICATION.md
```

Vključi:

- datum;
- SHA;
- Python verzijo;
- OS;
- ukaze;
- uspešne/neuspešne teste;
- morebitne manjkajoče lokalne modele;
- zadnji znani polni 156-case run;
- znane arhitekturne omejitve.

## 3.3 Ustvari ponovljivo arhivsko skripto

Dodaj:

```text
scripts/archive_rei_architecture.py
```

Skripta mora:

1. preveriti, da ni nenamernih necommitiranih sprememb;
2. prebrati source SHA;
3. uporabiti `git ls-files`, ne slepega kopiranja celotnega direktorija;
4. kopirati samo izbrane sledene datoteke;
5. izključiti:
   - `.git/`;
   - `archive/`;
   - `output/`;
   - cache;
   - lokalne prompt override;
   - loge;
   - `.venv`;
   - modele;
   - začasne datoteke;
6. izračunati SHA-256 vsake arhivirane datoteke;
7. ustvariti manifest;
8. zavrniti prepis obstoječega arhiva brez `--force`;
9. po kopiranju ponovno preveriti vse hashe.

Predlagani CLI:

```powershell
python scripts\archive_rei_architecture.py `
  --archive-id rei_v3_text_llm_baseline_2026-07-13 `
  --source-ref HEAD
```

## 3.4 Vsebina arhiva

Ciljni direktorij:

```text
archive/rei_v3_text_llm_baseline_2026-07-13/
```

Struktura:

```text
archive/rei_v3_text_llm_baseline_2026-07-13/
├── README.md
├── ARCHITECTURE.md
├── BASELINE_VERIFICATION.md
├── SOURCE_COMMIT
├── MANIFEST.json
├── FILES.sha256
├── snapshot/
│   ├── README.md
│   ├── CURRENT.md
│   ├── .gitignore
│   ├── app/
│   │   ├── backend/rei/
│   │   └── gui/
│   ├── scripts/
│   ├── knowledge/
│   ├── datasets/
│   ├── Docs/
│   │   ├── evals/
│   │   └── plans/
│   └── reference_tests/
└── artifacts/
    └── README.md
```

V `snapshot/reference_tests/` kopiraj trenutni `tests/`, vendar jih preimenuj oziroma postavi tako, da jih aktivni pytest ne odkrije.

V arhiv kopiraj vse sledene datoteke iz:

```text
app/backend/rei/
app/gui/
scripts/
tests/
knowledge/
datasets/
Docs/evals/
Docs/plans/
README.md
CURRENT.md
.gitignore
```

Ne kopiraj že obstoječega `archive/non_baseline_2026-05-21/` v novi arhiv.

Izvorni dokumenti v `Docs`, zlasti PDF in DOCX, ostanejo na svojem mestu. V arhivskem README zapiši njihove poti in hashe, če so sledeni, vendar jih ni treba podvajati.

## 3.5 Arhivski manifest

`MANIFEST.json` mora vsebovati najmanj:

```json
{
  "archive_id": "rei_v3_text_llm_baseline_2026-07-13",
  "source_commit": "...",
  "source_branch": "main",
  "created_at": "...",
  "dirty_tree_before_archive": false,
  "baseline": {
    "entrypoint": "ReiEngine.run_rei_cycle",
    "runner": "scripts/run_rei_profile_matrix.py",
    "matrix": "13 x 12 = 156",
    "architecture": "textual-three-processor-plus-ego-llm"
  },
  "known_designs": {
    "profiles": "continuous numeric weights",
    "synthesis": "EgoResultant LLM plus deterministic fallback",
    "acceptance": "keyword heuristic",
    "processor_input": "same text plus profile and influence weights"
  },
  "files": [
    {
      "source_path": "...",
      "archive_path": "...",
      "sha256": "...",
      "size_bytes": 0
    }
  ],
  "excluded_paths": [],
  "verification": {
    "pytest_command": "python -m pytest -q",
    "pytest_result": "...",
    "deterministic_smoke": "..."
  }
}
```

## 3.6 Arhivski opis arhitekture

`ARCHITECTURE.md` naj pošteno opiše:

- `ReiEngine.run_rei_cycle`;
- tri `REISignal` tekstovne modele;
- `profile_weights`;
- profile-aware procesorske payloade;
- `AcceptanceAssessment`;
- `EgoResultant`;
- situacijski driver in `resultant_leader_under_pressure`;
- prompt/contract loader;
- GUI;
- dataset workbench;
- 156-case matriko;
- prednosti starega sistema;
- znane probleme, zaradi katerih se arhitektura zamenjuje.

Ne spreminjaj zgodovine in ne predstavljaj starega sistema kot neuspeh. Bil je raziskovalni korak, ki je razkril omejitve treh tekstovnih agentov.

## 3.7 Izolacija arhiva

Dodaj oziroma dopolni `pytest.ini`:

```ini
[pytest]
norecursedirs =
    archive
    output
    .git
    .venv
```

Dodaj test:

```text
tests/test_archive_boundary.py
```

Ta naj preveri:

- aktivna koda ne uvaža ničesar iz `archive`;
- aktivni runnerji ne vsebujejo arhivskih poti;
- novi package ne uporablja legacy modulov;
- arhivske datoteke niso del aktivnega pytest discoveryja.

## 3.8 Stari načrti

Datoteko:

```text
Docs/plans/REI_v3_Codex_first_execution_prompt.md
```

kopiraj v arhiv.

Na vrh aktivne kopije dodaj jasno oznako:

```text
SUPERSEDED: this plan belongs to the archived textual/QLoRA direction.
See Docs/plans/REI_native_composition_architecture_upgrade_2026-07-13.md.
```

Ne briši je.

## 3.9 Prvi obvezni commit

Commit naj vsebuje samo arhiviranje in dokumentiranje baselinea.

Predlagan commit:

```text
chore(archive): freeze textual REI-v3 architecture before native-modalities rewrite
```

Pred tem pokaži:

```powershell
git diff --stat
git status --short
python -m pytest -q
```

Če ta commit vsebuje novo arhitekturno kodo, je faza izvedena napačno.

---

# 4. Del B — nova arhitektura

Delovno ime:

```text
REI Native Modalities & Ego Composition Architecture
```

Začasni package:

```text
app/backend/rei_next/
```

Stari aktivni package naj ostane nespremenjen, dokler nova arhitektura ne doseže predpisanih prehodnih pogojev.

Ob končnem cutoverju se `rei_next` promovira v `rei`.

---

# 5. Ciljna arhitektura

```text
                                  DOGODEK
                                     │
                                     ▼
                         GROUNDED PERCEPTION ROUTER
                                     │
                 ┌───────────────────┼───────────────────┐
                 │                   │                   │
                 ▼                   ▼                   ▼
         RACIO INPUT PACKET   EMOCIO INPUT PACKET  INSTINKT INPUT PACKET
                 │                   │                   │
                 ▼                   ▼                   ▼
         RACIO NATIVE          EMOCIO NATIVE        INSTINKT NATIVE
         PROCESSOR             VISUAL PROCESS       EMBODIED PROCESS
                 │                   │                   │
                 │             current/desired/      body state,
                 │             broken scenes,        danger, loss,
                 │             visual rollouts       trust, attachment
                 │                   │                   │
                 └───────────────────┼───────────────────┘
                                     ▼
                           FROZEN NATIVE BUNDLE
                                     │
                          ┌──────────┴──────────┐
                          ▼                     ▼
              CHARACTER GOVERNANCE      MANIFESTATION LAYER
              stable ordinal authority  images / urges / body signals
                          │                     │
                          ▼                     ▼
                 GOVERNANCE MANDATE      RACIO INTERPRETER
                          │                     │
                          └──────────┬──────────┘
                                     ▼
                           RACIO CONSCIOUS SPACE
                                     │
                                     ▼
                           CONSCIOUS DECISION
                                     │
                                     ▼
                            BEHAVIOR RESULTANT
                                     │
                                     ▼
                                  OUTCOME
                                     │
                                     ▼
                                EGO MEASURE
                                     │
                                     ▼
                           EGO TRACE / COMPOSITION
                         ┌───────────┼───────────┐
                         ▼           ▼           ▼
                    Racio world  Emocio world Instinkt world
                         └───────────┴───────────┘
                                     │
                                NEXT EVENT
```

Pomembno:

- `GovernanceMandate` ni četrta odločitev.
- Zavedna odločitev je vedno Racijeva.
- Mandat pove, kateri nativni sklep ima zaradi značaja oblast oziroma pritisk.
- Racio lahko ta sklep pravilno ali napačno razume.
- Zavedna odločitev, mandat in dejansko vedenje se lahko razhajajo.
- Ego je celotna časovna kompozicija tega dogajanja.

---

# 6. Predlagana struktura novega packagea

```text
app/backend/rei_next/
├── __init__.py
├── engine.py
├── config.py
├── errors.py
├── ids.py
├── models/
│   ├── common.py
│   ├── scene.py
│   ├── racio.py
│   ├── emocio.py
│   ├── instinkt.py
│   ├── character.py
│   ├── communication.py
│   ├── governance.py
│   ├── conscious.py
│   ├── ego.py
│   └── run.py
├── canon/
│   ├── loader.py
│   ├── glossary.py
│   └── validation.py
├── perception/
│   ├── router.py
│   ├── text_scene_parser.py
│   ├── evidence.py
│   └── packets.py
├── minds/
│   ├── base.py
│   ├── racio/
│   │   ├── processor.py
│   │   └── contracts.py
│   ├── emocio/
│   │   ├── processor.py
│   │   ├── scene_graph.py
│   │   ├── scene_memory.py
│   │   ├── rollout.py
│   │   ├── valuation.py
│   │   └── renderer.py
│   └── instinkt/
│       ├── processor.py
│       ├── body.py
│       ├── dynamics.py
│       ├── association_memory.py
│       ├── rollout.py
│       └── policy.py
├── communication/
│   ├── manifestations.py
│   ├── racio_interpreter.py
│   └── translation_gap.py
├── governance/
│   ├── profiles.py
│   ├── resolver.py
│   ├── delegation.py
│   ├── negotiation.py
│   └── behavior.py
├── conscious/
│   ├── committer.py
│   └── narrator.py
├── ego/
│   ├── measure.py
│   ├── trace_store.py
│   ├── composition.py
│   ├── projections.py
│   └── reflector.py
├── providers/
│   ├── protocols.py
│   ├── deterministic.py
│   ├── llm.py
│   ├── vision_language.py
│   ├── diffusion.py
│   └── embeddings.py
├── persistence/
│   ├── artifact_store.py
│   └── run_store.py
└── diagnostics/
    ├── invariants.py
    └── report.py
```

Ne ustvarjaj praznih datotek samo zaradi drevesa. Vsako fazo implementiraj vertikalno in z delujočimi testi.

---

# 7. Kanon nove arhitekture

Ustvari:

```text
knowledge/canon_v2/
├── claims.jsonl
├── glossary.yaml
├── racio.yaml
├── emocio.yaml
├── instinkt.yaml
├── character_profiles.yaml
├── acceptance.yaml
├── ego.yaml
└── open_questions.md
```

Slovenščina je kanonični jezik.

Vsak claim:

```json
{
  "claim_id": "C-RACIO-001",
  "canonical_sl": "...",
  "en_gloss": "...",
  "source_kind": "OD",
  "source_file": "Docs/REI osnova Racio.docx",
  "source_page": 1,
  "status": "direct_source",
  "scope": "racio",
  "implementation_effect": "...",
  "risk_class": "core"
}
```

Dovoljeni statusi:

```text
direct_source
source_synthesis
implementation_hypothesis
open_question
deprecated_hypothesis
```

Obvezno loči:

- teorijo;
- programsko operacionalizacijo;
- odprto vprašanje;
- metafizično trditev;
- varnostno občutljivo trditev.

V novi kanon ne prenesi:

- benchmark-specific pravil;
- quit-job/runway popravkov;
- keyword classifierjev;
- decimalnih profilnih uteži;
- avtomatskega situacijskega overridea.

---

# 8. Skupni podatkovni model

## 8.1 Osnovne oznake

```python
MindId = Literal["R", "E", "I"]
LanguageCode = Literal["sl", "en"]
SourceModality = Literal[
    "text",
    "image",
    "video",
    "audio",
    "body",
    "smell",
    "taste",
    "simulator",
]
```

## 8.2 Evidence in dogodek

```python
class EvidenceItem(BaseModel):
    id: str
    modality: SourceModality
    content: str
    grounded: bool
    source_ref: str
    confidence: float
    inferred_by: str | None = None

class DecisionOption(BaseModel):
    id: str
    label: str
    description: str = ""

class SceneEvent(BaseModel):
    event_id: str
    raw_input: str
    language: LanguageCode
    evidence: list[EvidenceItem]
    options: list[DecisionOption]
    actors: list[str]
    constraints: list[str]
    unknowns: list[str]
```

Pravilo:

> Vse, kar je izvirno podano, mora imeti provenance. Vse, kar model sklepa ali generira, mora biti označeno kot inferred.

## 8.3 Svetovi posameznih razumov

```python
class RacioWorld(BaseModel):
    explicit_beliefs: list[str]
    facts: list[str]
    rules: list[str]
    timelines: list[str]
    commitments: list[str]

class EmocioWorld(BaseModel):
    visual_memories: list[str]
    desired_scenes: list[str]
    broken_scenes: list[str]
    social_identity_motifs: list[str]
    attraction_patterns: list[str]
    motor_patterns: list[str]

class InstinktWorld(BaseModel):
    associations: list[str]
    trusted_patterns: list[str]
    threat_patterns: list[str]
    attachment_objects: list[str]
    unresolved_losses: list[str]
    boundary_patterns: list[str]
```

V realni implementaciji so lahko reference na artefakte ali embeddinge, ne samo besedilo.

## 8.4 Zamrznjeni bundle

```python
class NativeMindBundle(BaseModel):
    bundle_id: str
    scene_hash: str
    racio: RacioNativeConclusion
    emocio: EmocioNativeConclusion
    instinkt: InstinktNativeConclusion
    created_at: str
    immutable_hash: str
```

Po izdelavi bundlea se native zaključki ne smejo več spreminjati. Racijeva poznejša interpretacija je nov objekt.

---

# 9. Racio arhitektura

## 9.1 RacioNativeProcessor

Vhod:

- besede;
- številke;
- dejstva;
- čas;
- pravila;
- eksplicitne možnosti;
- posledice;
- Racijev svet;
- prejšnji Racijevi zapisi iz Ego projekcije.

Izhod:

```python
class RacioNativeConclusion(BaseModel):
    mind: Literal["R"] = "R"
    option_id: str | None
    facts_used: list[str]
    unknowns: list[str]
    causal_sequence: list[str]
    utility_structure: list[str]
    explicit_goal: str
    main_objection: str
    confidence: float
    abstains: bool = False
    uncertainty: str
```

Racio ne sme prejeti karakterja v kontroliranem načinu.

## 9.2 RacioInterpreter

Prejme samo zavestno dostopne manifestacije:

```text
EmocioManifestation
InstinktManifestation
```

Ne prejme:

```text
EmocioNativeConclusion.internal_motive
InstinktNativeConclusion.internal_association
```

Izhod:

```python
class RacioInterpretation(BaseModel):
    source_mind: Literal["E", "I"]
    observed_manifestations: list[str]
    inferred_option_id: str | None
    inferred_motive: str
    confidence: float
    alternative_hypotheses: list[str]
```

Sistem za evaluacijo lahko primerja interpretacijo z nativnim sklepom. Racio sam tega ground trutha ne vidi.

## 9.3 RacioCommitter

Racio vedno oblikuje:

```python
class ConsciousDecision(BaseModel):
    made_by: Literal["R"] = "R"
    option_id: str | None
    declared_reason: str
    conscious_confidence: float
    aligned_with_governance_mandate: bool | None
    decision_status: Literal[
        "committed",
        "deferred",
        "oscillating",
        "blocked",
        "unknown",
    ]
```

Pri sprejemanju lahko Racio pravilno sprejme sklep vodilnega E ali I.

Pri nesprejemanju lahko:

- sprejme lasten nasprotni sklep;
- napačno razloži isti sklep;
- odloži;
- racionalizira;
- misli, da je odločitev njegova, čeprav jo je sprožil drug razum.

## 9.4 RacioNarrator

Ločen od committerja.

Izhod:

```python
class RacioSelfNarrative(BaseModel):
    explanation: str
    claimed_motive: str
    acknowledged_minds: list[MindId]
    omitted_minds: list[MindId]
    uncertainty: str
```

Narrator ne sme spremeniti `ConsciousDecision` ali `BehaviorResultant`.

---

# 10. Emocio arhitektura

## 10.1 Emocio ni image generator

Image generator je:

```text
Emocievo platno oziroma renderer
```

Emocio kot sistem mora vsebovati:

```text
Visual Scene Compiler
Visual Scene Memory
Current Scene
Desired Scene
Broken Scene
Counterfactual Scene Rollouts
Visual Valuation
Native Policy
Optional Renderer
```

## 10.2 VisualSituationPacket

```python
class EmocioInputPacket(BaseModel):
    scene_id: str
    grounded_visual_cues: list[str]
    social_layout: list[str]
    actor_positions: list[str]
    observed_attention: list[str]
    movement_cues: list[str]
    aesthetic_cues: list[str]
    explicit_identity_cues: list[str]
    allowed_option_ids: list[str]
    evidence_ids: list[str]
    caveat: str
```

Router ne sme zapisati:

```text
Emocio želi ...
Emocio se boji ...
Emocio bo izbral ...
```

## 10.3 VisualSceneSpec

```python
class VisualSceneSpec(BaseModel):
    scene_id: str
    scene_kind: Literal[
        "current",
        "desired",
        "broken",
        "option_rollout",
    ]
    option_id: str | None
    entities: list[str]
    self_position: str
    attention_structure: dict[str, float]
    group_belonging: str
    status_relations: list[str]
    movement: list[str]
    composition: list[str]
    attraction_markers: list[str]
    obstacle_markers: list[str]
    grounded_evidence_ids: list[str]
    inferred_elements: list[str]
```

## 10.4 EmocioVisualState

```python
class EmocioVisualState(BaseModel):
    current_scene: VisualSceneSpec
    desired_scene: VisualSceneSpec
    broken_scene: VisualSceneSpec
    option_rollouts: dict[str, VisualSceneSpec]
```

## 10.5 Renderer

Protokol:

```python
class ImageRenderer(Protocol):
    def render(self, spec: VisualSceneSpec, seed: int) -> ImageArtifact: ...
```

Podprte implementacije pozneje:

- local Diffusers;
- ComfyUI API;
- drug local text-to-image ali image-to-image model;
- `NullRenderer` za teste.

`ImageArtifact` mora beležiti:

- model;
- model revision;
- seed;
- input spec hash;
- prompt;
- negative prompt;
- path;
- width/height;
- generated-only elements;
- grounded mask, če obstaja.

## 10.6 Pravilo proti slikovni halucinaciji

Generator lahko sliko estetsko dopolni, ne sme pa njegova izmišljena podrobnost postati dejstvo.

Zato:

```text
SceneEvent evidence > VisualSceneSpec > generated image
```

ne pa:

```text
generated image -> nova dejstva o dogodku
```

Če Racio na sliki opazi nekaj, kar ni v `VisualSceneSpec`, mora biti to označeno kot:

```text
renderer-added / ungrounded
```

in ne sme vplivati na native Emociev sklep.

## 10.7 EmocioValuator

Za vsako option scene oceni vsaj:

```text
ujemanje z želeno sliko
oddaljenost od porušene slike
vidnost sebe
pripadnost
pozornost
privlačnost
novost
gibanje
status
tekmovalni uspeh
možnost napada ali preboja
```

To je projektna operacionalizacija in mora biti označena kot `implementation_hypothesis`.

## 10.8 EmocioNativeConclusion

```python
class EmocioNativeConclusion(BaseModel):
    mind: Literal["E"] = "E"
    option_id: str | None
    desired_transformation: str
    current_scene_id: str
    desired_scene_id: str
    decisive_rollout_scene_id: str | None
    main_obstacle: str
    action_tendency: Literal[
        "approach",
        "perform",
        "compete",
        "connect",
        "attack",
        "improvise",
        "withdraw_contact",
        "unknown",
    ]
    valuation_dimensions: dict[str, float]
    intensity: float
    abstains: bool = False
    uncertainty: str
```

Ta objekt mora nastati pred Racijevo interpretacijo.

## 10.9 EmocioManifestation

Raciu je lahko dostopno:

- zavestna projekcija slike;
- privlačnost ali odpor;
- jeza;
- želja po približanju;
- motorni impulz;
- obrazni izraz;
- napetost zaradi porušene slike.

```python
class EmocioManifestation(BaseModel):
    visible_image_artifact_ids: list[str]
    attraction_intensity: float
    aversion_intensity: float
    anger_intensity: float
    motor_urge: str
    social_pull: str
```

Manifestacija ni isto kot Emociev celotni nativni sklep.

## 10.10 Prva izvedbena stopnja Emocia

V prvem PoC ne zahtevaj Stable Diffusion.

Najprej morajo delovati:

1. `VisualSceneSpec`;
2. option rollouts;
3. deterministic oziroma fake valuator;
4. native conclusion;
5. `NullRenderer`;
6. testi nespremenljivosti.

Šele nato priključi lokalni image generator.

Tako ločiš problem Emocievega procesiranja od problema kakovosti slik.

---

# 11. Instinkt arhitektura

## 11.1 Instinkt ni tekstovni svetovalec

Jedro Instinkta:

```text
Virtual Body
Interoceptive State
Associative Memory
Threat/Loss/Attachment Model
Option Body Rollouts
Protective Policy
```

Tekstovni LLM je lahko pomoč pri pretvorbi uporabnikovega besedila v grounded cue, ne sme biti Instinktov odločevalni center.

## 11.2 InstinktInputPacket

```python
class InstinktInputPacket(BaseModel):
    scene_id: str
    physical_cues: list[str]
    uncertainty_cues: list[str]
    trust_cues: list[str]
    boundary_cues: list[str]
    attachment_cues: list[str]
    scarcity_cues: list[str]
    escape_cues: list[str]
    explicit_body_cues: list[str]
    option_ids: list[str]
    evidence_ids: list[str]
    caveat: str
```

## 11.3 VirtualBody

```python
class BodyState(BaseModel):
    energy: float
    fatigue: float
    pain: float
    arousal: float
    tension: float
    physical_integrity: float
    uncertainty: float
    trust: float
    attachment_security: float
    resource_security: float
    boundary_integrity: float
    escape_availability: float
    predictability: float
```

Vse vrednosti so normalizirane v `[0, 1]`.

To niso karakterne uteži. So trenutno stanje simulatorja.

## 11.4 Instinktov asociativni spomin

```python
class InstinctAssociation(BaseModel):
    association_id: str
    cue_signature: list[str]
    body_state_before: BodyState
    felt_intensity: float
    protected_target: str
    experienced_loss: str | None
    action_taken: str
    outcome: str
    trust_delta: float
    attachment_delta: float
    boundary_delta: float
    decay: float
```

Spomin je lahko omejen, nezanesljiv in asociativen. Ne implementiraj ga kot popoln tekstovni kronološki RAG.

## 11.5 Body dynamics

```python
class BodyTransition(BaseModel):
    from_state: BodyState
    to_state: BodyState
    deltas: dict[str, float]
    triggering_evidence_ids: list[str]
```

Simulator naj bo v prvi verziji determinističen in konfigurabilen.

Vsa pravila morajo biti vidna v:

```text
knowledge/canon_v2/instinkt.yaml
```

in označena kot:

```text
direct_source
ali
implementation_hypothesis
```

## 11.6 Option rollout

```python
class InstinktOptionRollout(BaseModel):
    option_id: str
    trajectory: list[BodyState]
    dominant_alarm: str
    predicted_loss: float
    recoverability: float
    protected_targets: list[str]
    boundary_outcome: str
    trust_outcome: str
    attachment_outcome: str
    escape_outcome: str
```

## 11.7 InstinktNativeConclusion

```python
class InstinktNativeConclusion(BaseModel):
    mind: Literal["I"] = "I"
    option_id: str | None
    dominant_alarm: str
    danger_claims: list[str]
    protected_targets: list[str]
    action_tendency: Literal[
        "protect",
        "withdraw",
        "maintain",
        "set_boundary",
        "seek_safety",
        "seek_attachment",
        "conserve",
        "freeze",
        "unknown",
    ]
    minimum_safety_condition: str
    decisive_rollout_option_id: str | None
    intensity: float
    abstains: bool = False
    uncertainty: str
```

To so strukturirane trditve simulatorja, ne Instinktov slovenski notranji monolog.

## 11.8 InstinktManifestation

```python
class InstinktManifestation(BaseModel):
    body_locations: list[str]
    felt_tension: float
    fear_intensity: float
    attachment_pull: float
    withdrawal_urge: float
    freeze_intensity: float
    boundary_alarm: float
    raw_urge: str
```

Racio iz tega izdela svojo razlago.

## 11.9 Instinkt kot regulator skupnega stanja

Instinktovo stanje lahko vpliva na pogoje naslednjega procesiranja:

- ožji ali širši fokus;
- zaznana nujnost;
- dostopnost zaščitnih spominov;
- Racijev časovni horizont;
- Emocievo pričakovano sliko;
- pripravljenost telesa na gibanje.

Ne sme vplivati na:

```text
structural_character
authority_tiers
```

V prvi verziji uporabi enosmeren cikel:

```text
body state at t -> processors at t -> action/outcome -> body state at t+1
```

Ne uvajaj neskončnih agent loopov.

---

# 12. CharacterAuthority in governance

## 12.1 Profili

Implementiraj vseh 13:

```text
R>(E=I)
E>(R=I)
I>(R=E)

(R=E)>I
(R=I)>E
(E=I)>R

R>E>I
R>I>E
E>R>I
E>I>R
I>R>E
I>E>R

R=E=I
```

## 12.2 Model

```python
class CharacterAuthority(BaseModel):
    profile_id: str
    authority_tiers: list[list[MindId]]
    rule: Literal[
        "single_top",
        "ordered_top",
        "joint_top",
        "two_of_three",
    ]
```

## 12.3 Strukturni in učinkoviti položaj

```python
class ProcessorAvailability(BaseModel):
    R: float = 1.0
    E: float = 1.0
    I: float = 1.0

class EffectiveAuthority(BaseModel):
    structural_profile: CharacterAuthority
    effective_tiers: list[list[MindId]]
    override_reason: str | None
```

`effective_tiers` se spremeni samo pri eksplicitni funkcionalni okvari oziroma odsotnosti.

Prepovedano je spreminjanje zaradi:

- strahu;
- excitementa;
- keywords;
- visokega confidence;
- stresa;
- trenutne glasnosti;
- razpoloženja.

## 12.4 Pravila enega vodilnega razuma

Za:

```text
R>(E=I)
E>(R=I)
I>(R=E)
```

top razum poda governance mandate.

Druga dva:

- ostaneta prisotna;
- lahko nasprotujeta;
- lahko pomagata pri izvedbi;
- lahko sta preslišana;
- pri nesprejemanju lahko sabotirata;
- ne spremenita karakterja.

## 12.5 Tristopenjski profili

Pri:

```text
R>E>I
...
```

najvišji razum določi governance mandate.

Drugi razum je prvi kandidat za:

- korekcijo;
- izvedbo;
- delegacijo;
- nadomestitev ob funkcionalni nedostopnosti top razuma.

Tretji ostane kot ugovor, cena, zaščita ali drugačen pogled.

Ne uvajaj decimalnega kompromisa.

## 12.6 Parni profili

Pri:

```text
(R=E)>I
(R=I)>E
(E=I)>R
```

- če se vodilna razuma strinjata, nastane mandat;
- če se ne strinjata, je mandat nerešen;
- podrejeni razum ni avtomatski tie-breaker;
- rezultat je lahko zastoj, nihanje ali pogajalski cikel;
- eksplicitna delegacija lahko omogoči operativni korak brez spremembe hierarhije.

```python
class PairConflict(BaseModel):
    top_minds: list[MindId]
    option_by_mind: dict[MindId, str]
    status: Literal["resolved", "unresolved"]
    negotiation_rounds: int
```

Pogajalski cikel omeji na največ dve dodatni iteraciji. Vsaka iteracija mora dodati novo informacijo ali nov rollout. Brez nove informacije se cikel konča kot `unresolved`.

## 12.7 Trinajsti značaj

Pri:

```text
R=E=I
```

- dva enaka sklepa preglasita tretjega;
- vsi trije enaki pomenijo `simulated_spoznanje`;
- vsi trije različni pomenijo `unresolved`;
- Racio nima dodatnega glasu zato, ker je zavesten;
- confidence ne poveča števila glasov.

## 12.8 GovernanceMandate

```python
class GovernanceMandate(BaseModel):
    status: Literal[
        "resolved",
        "unresolved",
        "delegated",
        "functionally_overridden",
    ]
    structural_source_minds: list[MindId]
    option_id: str | None
    objections: dict[MindId, str]
    delegation: TaskDelegation | None
    hidden_native_motives: dict[MindId, str]
```

`hidden_native_motives` se hranijo v traceu. Ne pošiljaj jih RacioInterpreterju kot ground truth.

---

# 13. ConsciousDecision in BehaviorResultant

To sta ločena objekta.

## 13.1 Zakaj

Primer:

```text
Racio se zavestno odloči za novoletno zaobljubo.
Emocio in Instinkt je ne sprejmeta.
Človek zavestno govori eno, dejansko ravnanje pa ne sledi.
```

Drugi primer:

```text
Emocio določi smer.
Racio to smer zavestno sprejme, vendar si izmisli drug razlog.
Vedenje je skladno, razlaga pa je napačna.
```

## 13.2 BehaviorResultant

```python
class BehaviorResultant(BaseModel):
    option_id: str | None
    status: Literal[
        "executed",
        "delayed",
        "oscillating",
        "sabotaged",
        "blocked",
        "unresolved",
    ]
    governance_alignment: str
    conscious_alignment: str
    operational_controller: MindId | None
    residual_tensions: list[str]
    predicted_action: str
```

## 13.3 Začetna transparentna pravila

Ne uporabljaj LLM-ja za odločanje o tem.

V prvi implementaciji uporabi eksplicitno tabelo:

### Sprejemajoče sodelovanje

- če je mandat rešen, Racio ga zavestno sprejme;
- razlog je lahko napačno preveden, vendar je dejanje koordinirano;
- podrejeni ugovori so priznani;
- dovoljena je delegacija.

### Mešano stanje

- Racio sledi mandatu samo, če pravilno prepozna usmeritev vodilnega E/I;
- sicer se lahko odloči drugače in nastane delay ali oscillation;
- rezultat mora jasno prikazati razliko.

### Konfliktno nesprejemanje

- Racio lahko zavestno sprejme svoj sklep;
- governance mandate lahko ostane drug;
- vedenje je lahko sabotirano, blokirano ali ciklično;
- nikoli ne prikrij razhajanja z enim `integrated_decision` stavkom.

Ta tabela je implementacijska hipoteza in mora biti konfigurirana, ne skrita po kodi.

---

# 14. AcceptanceState

## 14.1 Model odnosa

```python
class DirectedMindRelation(BaseModel):
    visibility: float
    interpretation_fidelity: float
    tolerance: float
    delegation_willingness: float
    sabotage_risk: float

class AcceptanceState(BaseModel):
    R_to_E: DirectedMindRelation
    R_to_I: DirectedMindRelation
    E_to_R: DirectedMindRelation
    E_to_I: DirectedMindRelation
    I_to_R: DirectedMindRelation
    I_to_E: DirectedMindRelation
    overall_mode: Literal[
        "accepting",
        "mixed",
        "conflicted",
        "unknown",
    ]
```

V kontroliranih testih je AcceptanceState eksplicitni input.

V prvi verziji ga ne sklepaj iz keywordov.

## 14.2 TranslationGap

```python
class TranslationGap(BaseModel):
    source_mind: Literal["E", "I"]
    native_option_id: str | None
    interpreted_option_id: str | None
    native_motive_summary: str
    interpreted_motive: str
    option_match: bool
    motive_fidelity: float
    distortion_type: Literal[
        "none",
        "omission",
        "rationalization",
        "minimization",
        "projection",
        "misclassification",
        "unknown",
    ]
```

Ta objekt je v diagnostičnem traceu. Ni neposredno zaveden Raciu.

---

# 15. Ego kot skladba

## 15.1 Ego ni samo podatkovna baza

Skladba ni niti en ton niti notni zapis niti glasbenik.

Računalniški približek Ega ima tri plasti:

```text
EgoMeasure              en takt oziroma en cikel
EgoTrace                izvedena skladba skozi čas
EgoCompositionSnapshot  trenutno prepoznana struktura skladbe
```

## 15.2 EgoMeasure

```python
class EgoMeasure(BaseModel):
    measure_id: str
    event_id: str
    native_bundle_id: str
    structural_character: CharacterAuthority
    effective_authority: EffectiveAuthority
    acceptance_state: AcceptanceState

    governance_mandate: GovernanceMandate
    racio_interpretations: list[RacioInterpretation]
    conscious_decision: ConsciousDecision
    behavior_resultant: BehaviorResultant
    outcome: OutcomeRecord | None

    translation_gaps: list[TranslationGap]
    unresolved_tensions: list[str]
    spoznanje_status: Literal[
        "simulated_spoznanje",
        "partial_agreement",
        "no_spoznanje",
        "unknown",
    ]
```

## 15.3 EgoTrace

Append-only event store:

```python
class EgoTrace(BaseModel):
    ego_id: str
    measures: list[EgoMeasure]
```

Pravila:

- prejšnji measure se ne spreminja;
- popravki so novi correction events;
- vsak measure ima hash;
- trace je mogoče reproducirati;
- noben measure nima `ego_vote`.

## 15.4 EgoCompositionSnapshot

```python
class EgoCompositionSnapshot(BaseModel):
    ego_id: str
    through_measure_id: str
    identity_motifs: list[str]
    recurring_conflicts: list[str]
    recurring_translation_errors: list[str]
    unresolved_tensions: list[str]
    resolved_tensions: list[str]
    spoznanja: list[str]
    commitments: list[str]
    relationship_patterns: list[str]
    current_section: str
    evidence_measure_ids: list[str]
```

Snapshot je izpeljan iz tracea. Ni izvor resnice in ni agent.

## 15.5 EgoProjection

Dosedanja skladba se vrne posameznim razumom v njihovi modalnosti:

```text
RacioProjection
    kronologija, dejstva, izjave, obljube, vzročne povezave

EmocioProjection
    ponavljajoči se prizori, podobe, statusne slike,
    trenutki pripadnosti, uspeha, porušitve in želje

InstinktProjection
    telesne posledice, nevarnosti, izgube, zaupanje,
    navezanost, meje, pomanjkanje in okrevanje
```

S tem Ego vpliva na naslednji cikel, ne da bi izrekel četrto mnenje.

## 15.6 EgoReflector

Opcijski LLM:

```python
class EgoReflector:
    def summarize_patterns(trace, snapshot) -> ReflectionHypothesis: ...
```

Omejitve:

- ne sodeluje v trenutni odločitvi;
- ne spremeni native conclusion;
- ne spremeni governance mandate;
- ne zapisuje neposredno v svetove brez provenance;
- njegov izhod je hipoteza;
- mora navesti measure IDs, na katerih temelji.

## 15.7 Življenje

Življenje v tej nadgradnji ni runtime agent.

Ne implementiraj:

```text
LifeAgent
LifeDecision
LifePrompt
```

Metafizična plast ostane v kanonu kot ločeno raziskovalno področje. Nova arhitektura naj pusti extension point, ne pa simulira avtoritete, ki je ne znamo operativno definirati.

---

# 16. End-to-end cikel

Nova metoda:

```python
ReiNativeEngine.run_cycle(...)
```

Predlagani tok:

1. naloži `PersonState`;
2. naloži `EgoCompositionSnapshot`;
3. izdela tri modalno različne projekcije preteklosti;
4. normalizira `SceneEvent`;
5. izdela tri ločene input packete;
6. vzporedno izvede RacioNative, EmocioNative in InstinktNative;
7. validira in zamrzne `NativeMindBundle`;
8. izračuna agreement pattern;
9. uporabi `CharacterAuthority`;
10. izdela `GovernanceMandate`;
11. izdela Emocio in Instinkt manifestaciji;
12. Racio interpretira manifestaciji;
13. Racio oblikuje `ConsciousDecision`;
14. deterministični `BehaviorResolver` izdela `BehaviorResultant`;
15. opcijski zunanji simulator vrne `OutcomeRecord`;
16. ustvari `EgoMeasure`;
17. append v `EgoTrace`;
18. posodobi `EgoCompositionSnapshot`;
19. izdela ločene projekcije za R, E in I;
20. shrani vse artefakte in diagnostiko.

## 16.1 Kontrolirani način

```python
mode="controlled_profile_matrix"
```

- isti `SceneEvent`;
- isti trije svetovi;
- isti frozen native bundle;
- vseh 13 karakterjev;
- brez ponovnega izvajanja procesorjev.

To meri samo vpliv značajske oblasti.

## 16.2 Longitudinalni način

```python
mode="person_longitudinal"
```

- karakter ostaja isti;
- vsak cikel spremeni svetove;
- različni karakterji skozi različne odločitve ustvarjajo različne zgodovine;
- kasnejši native sklepi se zato lahko razlikujejo;
- profil še vedno ni neposredno poslan native procesorju.

---

# 17. Provider protokoli

Core ne sme biti vezan na en model ali runtime.

```python
class TextReasoner(Protocol): ...
class VisionLanguageInterpreter(Protocol): ...
class ImageRenderer(Protocol): ...
class ImageEncoder(Protocol): ...
class VisualWorldModel(Protocol): ...
class BodyDynamicsModel(Protocol): ...
class ArtifactStore(Protocol): ...
class EgoTraceStore(Protocol): ...
```

Obvezne testne implementacije:

```text
DeterministicRacioProvider
DeterministicEmocioProvider
DeterministicInstinktProvider
NullImageRenderer
FakeVisionLanguageInterpreter
InMemoryEgoTraceStore
FileArtifactStore
```

Brez deterministic adapterjev arhitekture ni mogoče zanesljivo testirati.

---

# 18. Artefakti posameznega runa

Shranjuj:

```text
output/runs/{run_id}/
├── run_manifest.json
├── scene/
│   ├── event.json
│   ├── racio_packet.json
│   ├── emocio_packet.json
│   └── instinkt_packet.json
├── native/
│   ├── bundle.json
│   ├── racio.json
│   ├── emocio.json
│   └── instinkt.json
├── emocio/
│   ├── visual_state.json
│   ├── scenes/
│   └── images/
├── instinkt/
│   ├── body_before.json
│   ├── option_rollouts.json
│   └── body_after.json
├── communication/
│   ├── manifestations.json
│   ├── interpretations.json
│   └── translation_gaps.json
├── governance/
│   ├── character.json
│   ├── mandate.json
│   └── delegation.json
├── conscious/
│   ├── decision.json
│   └── narrative.json
├── behavior/
│   └── resultant.json
├── ego/
│   ├── measure.json
│   └── composition_snapshot.json
└── diagnostics/
    ├── invariants.json
    └── report.md
```

`run_manifest.json` beleži:

- source commit;
- canon version;
- profile;
- acceptance config;
- provider IDs;
- model revisions;
- seeds;
- hashes native artefaktov;
- čas;
- warnings;
- safety flags.

---

# 19. Testna strategija

## 19.1 Arhivski testi

```text
test_archive_manifest_complete
test_archive_hashes_match
test_archive_source_commit_matches
test_active_code_does_not_import_archive
test_pytest_ignores_archive
```

## 19.2 Domain testi

```text
test_scene_evidence_has_provenance
test_native_bundle_is_immutable
test_racio_is_only_conscious_mind
test_emocio_native_precedes_racio_interpretation
test_instinkt_native_precedes_verbalization
test_ego_has_no_vote_or_preferred_option
```

## 19.3 Karakterni testi

```text
test_all_13_profiles_parse
test_single_top_always_keeps_structural_authority
test_ordered_top_never_loses_rank_to_intensity
test_pair_agreement_resolves
test_pair_conflict_is_unresolved
test_subordinate_does_not_tiebreak_pair
test_thirteenth_uses_two_of_three
test_thirteenth_all_different_is_unresolved
test_all_three_same_is_simulated_spoznanje
test_physical_unavailability_changes_effective_not_structural_authority
```

## 19.4 Racio testi

```text
test_racio_native_does_not_receive_profile
test_racio_interpreter_cannot_access_hidden_native_motive
test_racio_interpretation_can_be_wrong
test_conscious_decision_made_by_racio
test_narrator_cannot_mutate_decision
```

## 19.5 Emocio testi

```text
test_visual_router_does_not_preselect_emocio_option
test_current_desired_broken_scenes_exist
test_option_rollouts_share_grounded_identity
test_renderer_failure_does_not_remove_native_conclusion
test_renderer_added_detail_cannot_become_scene_fact
test_racio_caption_does_not_change_emocio_native_option
```

## 19.6 Instinkt testi

```text
test_body_transition_is_deterministic
test_same_event_different_body_state_can_change_instinkt_conclusion
test_body_state_never_changes_character
test_instinkt_output_is_structured_not_native_text_monologue
test_association_memory_has_decay
test_option_rollout_records_loss_and_recoverability
```

## 19.7 Acceptance testi

```text
test_disagreement_can_be_accepting
test_agreement_can_be_non_accepting
test_acceptance_does_not_change_authority
test_high_fidelity_reduces_translation_gap
test_sabotage_changes_behavior_not_structural_character
```

## 19.8 Ego testi

```text
test_ego_trace_is_append_only
test_ego_measure_contains_full_cycle
test_ego_snapshot_cites_measure_ids
test_ego_reflector_cannot_decide
test_racio_self_narrative_can_diverge_from_composition
test_ego_projections_are_modality_specific
```

## 19.9 Kontrafaktualna matrika

Za najmanj 12 ročno pripravljenih native bundle fixturejev:

- poženi vseh 13 karakterjev;
- ne ponovno izvajaj procesorjev;
- preveri governance mandate;
- preveri conscious/behavior divergence;
- preveri pair conflict;
- preveri 13th majority;
- preveri spoznanje.

To je nova osnovna matrika. Ne meri slogovnih razlik, temveč kavzalne razlike.

---

# 20. Prvi canonical fixtureji

Dodaj najmanj:

```text
tests/fixtures/native_bundles/
├── job_abroad.json
├── public_speaking.json
├── harmful_relationship.json
├── boundary_violation.json
├── expensive_purchase.json
├── creative_project.json
├── grief_and_work.json
├── moral_disclosure.json
├── family_loyalty.json
├── immediate_physical_danger.json
├── two_top_minds_conflict.json
└── all_three_same_spoznanje.json
```

Vsak fixture vsebuje:

- isti grounded scene;
- tri ločene native conclusions;
- pričakovane razloge;
- pričakovane profile, ki izberejo posamezne možnosti;
- odprta vprašanja;
- ali je pričakovano spoznanje.

Fixture ni dataset za trening. Je arhitekturna resnica za preverjanje kode.

---

# 21. GUI nove arhitekture

Nova delovna površina naj bo sprva:

```text
app/gui_next/
```

Prikaže štiri ločene ravni.

## 21.1 Native panel

### Racio

- dejstva;
- neznanke;
- časovnica;
- utility struktura;
- native option.

### Emocio

- current scene;
- desired scene;
- broken scene;
- option rollouts;
- slike;
- valuation;
- native option.

### Instinkt

- telo pred dogodkom;
- option body rollouts;
- glavni alarm;
- izguba;
- meja;
- zaupanje;
- navezanost;
- native option.

## 21.2 Communication panel

- Emocio manifestation;
- Instinkt manifestation;
- Racijeva interpretacija;
- native ground truth samo v debug načinu;
- translation gap;
- opozorilo, da Racio ground trutha v realnem ciklu ne vidi.

## 21.3 Character panel

- structural profile;
- authority tiers;
- processor availability;
- effective authority;
- governance mandate;
- pair conflict;
- 13th majority;
- delegation;
- conscious decision;
- behavior resultant.

## 21.4 Ego panel

- EgoMeasure;
- EgoTrace timeline;
- ponavljajoči se motivi;
- nerazrešene napetosti;
- ponavljajoče se napake prevajanja;
- Racio self-narrative vs composition snapshot;
- spoznanja;
- projekcije v tri svetove.

GUI ne sme avtomatsko izdelovati datasetov ali training primerov v tej fazi.

---

# 22. Faze izvedbe in commit načrt

## Faza A0 — preflight

Naloge:

- preveri HEAD in dirty tree;
- ustvari vejo;
- zaženi trenutne teste;
- zapiši baseline;
- ne spremeni kode.

Izhod:

```text
preflight report
```

Brez commita, če ni sprememb.

## Faza A1 — arhiv

Naloge:

- arhivska skripta;
- arhivski snapshot;
- manifest in hashi;
- baseline verification;
- pytest exclusion;
- archive boundary test;
- superseded oznaka starega plana.

Commit:

```text
chore(archive): freeze textual REI-v3 architecture before native-modalities rewrite
```

Izhodni pogoj:

- hashi se ujemajo;
- trenutni test suite uspe;
- aktivno vedenje se ni spremenilo.

## Faza B1 — arhitekturni dokumenti in kanon v2

Dodaj:

```text
Docs/architecture/REI_NATIVE_COMPOSITION_ARCHITECTURE.md
Docs/architecture/ADR-001-native-modalities.md
Docs/architecture/ADR-002-racio-conscious-decision.md
Docs/architecture/ADR-003-ordinal-character-governance.md
Docs/architecture/ADR-004-ego-as-composition.md
Docs/architecture/ADR-005-acceptance-is-orthogonal.md
knowledge/canon_v2/
```

Commit:

```text
docs(architecture): define native REI processors and Ego composition
```

Izhodni pogoj:

- vsak core claim je sledljiv;
- odprta vprašanja niso predstavljena kot dejstva;
- QLoRA ni v izvedbenem obsegu.

## Faza B2 — domain modeli in protokoli

Implementiraj:

- scene/evidence;
- mind packets;
- native conclusions;
- character;
- governance;
- conscious;
- ego models;
- provider protocols;
- immutable hash support.

Commit:

```text
feat(core): add REI native domain model and provider protocols
```

Izhodni pogoj:

- modeli se serializirajo;
- bundle je immutable;
- Ego nima decision API-ja;
- Racio je edini conscious type.

## Faza B3 — ordinalna governance in fixture matrika

Implementiraj:

- 13 profile parser;
- resolver;
- pair conflict;
- 13th majority;
- spoznanje;
- availability;
- delegation;
- canonical fixtures.

Commit:

```text
feat(governance): implement ordinal character authority and causal fixture matrix
```

Izhodni pogoj:

- 100 % governance truth-table testov;
- brez float uteži v odločanju;
- brez situacijskega overridea.

## Faza B4 — EgoMeasure, EgoTrace in composition skeleton

Implementiraj:

- append-only trace;
- measure;
- composition snapshot;
- modality projections;
- in-memory in file store;
- brez LLM reflectorja.

Commit:

```text
feat(ego): model Ego as append-only composition across REI cycles
```

Izhodni pogoj:

- Ego ne odloča;
- snapshot je izpeljan;
- vsaka trditev v snapshotu ima measure IDs.

## Faza B5 — Racio native

Implementiraj:

- Racio packet;
- deterministic Racio;
- LLM protocol adapter;
- native conclusion;
- brez interpretation in commit faze.

Commit:

```text
feat(racio): add independent verbal-analytical native processor
```

Izhodni pogoj:

- Racio ne vidi profila;
- fact/unknown/sequence pravilno ločeni;
- fixture smoke uspe.

## Faza B6 — Emocio structured core

Implementiraj:

- visual packets;
- scene graph;
- current/desired/broken;
- option rollouts;
- deterministic valuator;
- native conclusion;
- NullRenderer.

Commit:

```text
feat(emocio): add visual scene world model and native policy
```

Izhodni pogoj:

- Emocio izbere option pred Racijevo interpretacijo;
- renderer ni potreben za rezultat;
- image hallucination invariant uspe.

## Faza B7 — Emocio renderer

Implementiraj:

- provider protocol;
- local renderer adapter;
- image-to-image možnost;
- artifacts;
- reproducible seed;
- graceful fallback.

Commit:

```text
feat(emocio): integrate optional local visual rendering artifacts
```

Izhodni pogoj:

- neuspeh generatorja ne uniči cikla;
- slike imajo provenance;
- native option se po captioningu ne spremeni.

## Faza B8 — Instinkt virtual body

Implementiraj:

- BodyState;
- transitions;
- association memory;
- option rollouts;
- policy;
- native conclusion;
- manifestation.

Commit:

```text
feat(instinkt): add embodied protective simulator and associative memory
```

Izhodni pogoj:

- deterministični body testi;
- isti dogodek z drugim body stateom lahko spremeni I;
- karakter ostaja nespremenjen.

## Faza B9 — komunikacija in Racio interpretation

Implementiraj:

- manifestations;
- multimodal interpreter protocol;
- Racio interpretations;
- translation gap;
- acceptance fidelity.

Commit:

```text
feat(communication): model Racio translation of Emocio and Instinkt
```

Izhodni pogoj:

- Racio nima dostopa do hidden native motives;
- napačen prevod je mogoč in izmerjen;
- interpretacija ne mutira native bundlea.

## Faza B10 — conscious decision in behavior

Implementiraj:

- RacioCommitter;
- RacioNarrator;
- explicit behavior rule table;
- ConsciousDecision;
- BehaviorResultant;
- conscious/mandate/behavior divergence.

Commit:

```text
feat(conscious): separate Racio decision, governance mandate and behavior
```

Izhodni pogoj:

- vsak conscious decision je R;
- narrator ne spremeni odločitve;
- nesprejemanje je vidno kot razhajanje, ne skrito v kompromisu.

## Faza B11 — ReiNativeEngine

Implementiraj celoten cikel.

Dodaj:

```text
scripts/run_rei_native_cycle.py
scripts/run_rei_native_profile_matrix.py
```

Commit:

```text
feat(engine): orchestrate native REI cycle and Ego composition
```

Izhodni pogoj:

- end-to-end deterministic run;
- 13-profile frozen-bundle matrix;
- popoln artifact tree;
- nobena aktivna komponenta ne uvaža legacy kode.

## Faza B12 — GUI next

Implementiraj native, communication, character in Ego panele.

Commit:

```text
feat(gui): add multimodal REI composition workbench
```

Izhodni pogoj:

- človek vidi razliko med native signalom in Racijevo interpretacijo;
- Emocio slike in Instinkt body trajectory sta vidna;
- debug ground truth je jasno označen.

## Faza B13 — cutover

Šele po vseh gateih:

1. arhivski test uspe;
2. novi core testi uspejo;
3. deterministic end-to-end uspe;
4. native profile matrix uspe;
5. GUI smoke uspe.

Nato:

- odstrani oziroma arhiviraj preostale aktivne legacy entrypointe;
- promoviraj `app/backend/rei_next/` v `app/backend/rei/`;
- promoviraj `app/gui_next/` v `app/gui/`;
- posodobi import poti;
- posodobi README in CURRENT;
- stari runner nadomesti z deprecation wrapperjem ali ga pusti samo v arhivu;
- zaženi vse teste.

Commit:

```text
refactor!: promote native-modalities REI architecture to active runtime
```

V commit body zapiši:

```text
BREAKING CHANGE: the textual three-LLM EgoResultant baseline is archived and no longer the active runtime.
```

## Faza B14 — finalna verifikacija

Pripravi:

```text
Docs/evals/rei_native_architecture_acceptance_2026-07-13.md
```

Vključi:

- archive integrity;
- test results;
- architecture invariants;
- canonical fixture matrix;
- known limitations;
- model integrations, ki še manjkajo;
- odprta vprašanja;
- seznam vseh commitov;
- navodila za rollback na tag.

Commit:

```text
docs: record native REI architecture acceptance and rollback path
```

---

# 23. Kaj je izven obsega

Codex v tej nadgradnji ne sme:

- izdelovati QLoRA adapterjev;
- generirati training datasetov;
- izbirati končnega base modela;
- trenirati Stable Diffusion LoRA;
- izdelovati psihološke diagnoze;
- določati značaja resničnih oseb;
- implementirati Življenje kot agenta;
- izpeljevati medicinskih trditev;
- spreminjati izvornih dokumentov;
- uvajati agent loopov brez omejitve;
- uporabljati LLM kot skriti tie-breaker;
- zamenjati odprtega vprašanja s samozavestno programsko predpostavko.

---

# 24. Obvezne prepovedi v kodi

Dodaj statične oziroma testne varovalke za naslednje vzorce:

```text
profile_weight * confidence
situational_driver bonus
EgoAgent
ego_vote
ego_preferred_option
processor prompt contains character_profile
Racio interpreter receives native hidden motive
generated image adds grounded evidence
acceptance inferred from "bounded" or "reversible"
subordinate mind breaks pair tie
confidence changes authority tier
```

Kjer avtomatska statična kontrola ni smiselna, dodaj test ali arhitekturni komentar.

---

# 25. Kakovost kode

- Python tipizacija mora biti stroga.
- Pydantic modeli naj imajo `extra="forbid"`.
- Vsi artifact objekti morajo imeti schema version.
- Vsi ID-ji morajo biti stabilni in sledljivi.
- Vsi model/provider klici morajo beležiti model, revizijo, seed in parametre.
- Vsi zunanji providerji morajo imeti timeout in jasen fallback.
- Native bundle se po izdelavi ne sme mutirati.
- Noben LLM output ne sme samovoljno prepisati deterministične governance.
- Varnostni caveat naj ostane del javnega API-ja.
- Slovenski REI termini naj ostanejo kanonični.
- JSON ključi so lahko angleški.
- Komentarji naj pojasnjujejo arhitekturne razloge, ne ponavljajo kode.

---

# 26. Poročilo Codexa po vsaki fazi

Uporabi ta format:

```text
Phase:
Source SHA:
Changed files:
New files:
Deleted files:
Behavioral changes:
Tests run:
Tests passed:
Tests failed:
Artifacts created:
Open questions:
Architecture assumptions introduced:
Next recommended phase:
Proposed commit message:
```

Če Codex uvede novo hipotezo, jo mora zapisati tudi v:

```text
knowledge/canon_v2/open_questions.md
```

ali kot `implementation_hypothesis` v claim registry.

---

# 27. Končni Definition of Done

Nova arhitektura je sprejeta samo, če velja vse:

- stara arhitektura je arhivirana, označena s tagom in hash manifestom;
- rollback pot je dokumentirana;
- aktivna koda ne uvaža arhiva;
- native procesorji so modalno ločeni;
- Racio je jezikovno-simbolni procesor;
- Emocio izdela in ovrednoti prizore pred Racijevo interpretacijo;
- Instinkt izdela telesne rolloute in zaščitni sklep pred verbalizacijo;
- isti frozen bundle se lahko požene skozi vseh 13 značajev;
- karakter je ordinalen in stabilen;
- stanje in intenzivnost ne spreminjata karakterja;
- parni konflikt ne dobi umetnega tie-breakerja;
- trinajsti uporablja 2-of-3;
- `simulated_spoznanje` zahteva vse tri;
- zavestna odločitev je vedno Racijeva;
- governance mandate, conscious decision in behavior so ločeni;
- translation gap je eksplicitno merljiv;
- sprejemanje ne pomeni nujno soglasja;
- Ego nima glasu ali vote API-ja;
- EgoMeasure predstavlja en takt;
- EgoTrace predstavlja izvedeno zgodovino;
- EgoCompositionSnapshot prepoznava motive in napetosti;
- Ego projekcije se vrnejo trem razumom v različnih modalnostih;
- GUI jasno pokaže native signal, manifestacijo in Racijevo razlago;
- vsi canonical fixture in invariant testi uspejo;
- QLoRA ni del implementacije.

---

# 28. Prvi neposredni ukaz Codexu

Codex naj po prejemu tega dokumenta začne samo z Delom A.

```text
Preglej celoten dokument
Docs/plans/REI_native_composition_architecture_upgrade_2026-07-13.md.

Izvedi Fazo A0 in Fazo A1.

Najprej preveri dejanski HEAD, git status in obstoječi testni paket.
Nato arhiviraj trenutno tekstovno REI-v3 arhitekturo v
archive/rei_v3_text_llm_baseline_2026-07-13/.

Arhiv mora vsebovati:
- source commit;
- reproducibilno arhivsko skripto;
- snapshot aktivne kode, GUI-ja, skript, knowledge, dataset metapodatkov,
  eval dokumentacije in referenčnih testov;
- SHA-256 manifest;
- baseline verification;
- pošten opis trenutne arhitekture in znanih omejitev;
- rollback navodila.

Dodaj pytest/archive isolation in test, ki preprečuje aktivne importe iz arhiva.
Stari canonical-v2/QLoRA prompt označi kot superseded in ga kopiraj v arhiv.

V tej fazi ne dodajaj app/backend/rei_next in ne spreminjaj runtime vedenja.
Ne spreminjaj engine.py, models.py, profiles.py, acceptance.py ali aktivnih promptov,
razen če je sprememba nujna izključno za arhivsko izolacijo.

Zaženi:
- python -m pytest -q
- hash verification arhiva
- deterministic smoke, če je dosegljiv brez zunanjega modela

Pripravi en sam commit:
chore(archive): freeze textual REI-v3 architecture before native-modalities rewrite

Po commitu se ustavi in poročaj po predpisanem formatu.
Ne nadaljuj v novo arhitekturo, dokler arhivski commit ni čist in preverjen.
```

---

# 29. Najpomembnejši konceptualni povzetek

Nova arhitektura ni:

```text
štirje LLM agenti, ki se pogovarjajo
```

Nova arhitektura je:

```text
Racio    igra z jezikom, simboli in časom.
Emocio   igra s prizori, podobami in gibanjem.
Instinkt igra s telesom, nevarnostjo, izgubo in varovanjem.

Karakter določa stalno razporeditev njihove oblasti.
Sprejemanje določa, kako dobro se poslušajo in sodelujejo.
Racio edini vse skupaj zavedno ubesedi in sprejme zavestno odločitev.
En cikel je en takt.
Ego je skladba, ki jo ti trije igrajo skozi čas.
```

To je cilj nadgradnje.
