# REI-v3: kanonična arhitektura, dvojezični dataset in QLoRA načrt

**Namen dokumenta:** neposredna izvedbena specifikacija za Codex  
**Repozitorij:** `kotlet13/rei-v3`  
**Pregledani commit:** `995b572c893058c82d265d978a0391e317f1ea67`  
**Datum načrta:** 2026-07-10  
**Cilj:** zgraditi sistem, ki ločeno simulira procesiranje Racia, Emocia in Instinkta ter iz njihovih presoj po pravilih enega od 12 + 1 značajev izdela razložljivo končno odločitev.

---

## 0. Navodilo Codexu pred začetkom

Ta dokument ni predlog za en sam velik refactor. Izvajaj ga po fazah in po vsaki fazi:

1. zaženi vse obstoječe in nove teste;
2. zapiši, kaj si spremenil;
3. navedi odprta vprašanja;
4. pripravi majhen, pregleden commit;
5. ne nadaljuj v naslednjo fazo, dokler trenutna faza nima izpolnjenih izhodnih pogojev.

Ne spreminjaj obstoječega 156-case baseline vedenja v prvih dveh fazah. Nova arhitektura naj se sprva razvija vzporedno za feature flagom oziroma ločenim entrypointom.

**Prvo pravilo projekta:** QLoRA ne sme popravljati napačne arhitekture. Adapter je namenjen boljšemu procesiranju posameznega razuma in bolj zvestemu izrazoslovju. Pravila značaja, hierarhije in odločanja morajo biti eksplicitna, testljiva in v osrednjem delu deterministična.

---

# 1. Popravek dosedanje konceptualne smeri

Po neposrednem branju osnovnih dokumentov in 212-stranskega dokumenta *Eros - pogovori.pdf* je treba popraviti del sedanje projektne interpretacije.

Dokument `Docs/REI_weighted_synthesis_working_note.md` pravi, da je končni rezultat vedno gladek, utežen kompromis vseh treh razumov. Novi pregled primarnih virov tega ne podpira dovolj dobro.

## 1.1 Kaj viri povedo precej neposredno

### A. Značaj je stabilno, ordinalno razmerje moči

Osnovni dokument pravi, da se razmerje moči med tremi razumi vzpostavi med odraščanjem in za življenje določi značaj. V Erosovih komentarjih je to večkrat dodatno pojasnjeno kot nespremenljiv način oziroma pot procesiranja.

Najpomembnejši odlomek je na strani 88 dokumenta *Eros - pogovori.pdf*:

- pomembno je **razmerje** moči, ne absolutna številčna razlika;
- ni pomembno, ali je en razum malo ali veliko močnejši;
- močnejši v obeh primerih odloči;
- pri treh enakovrednih razumih zmaga odločitev, ki jo podpreta vsaj dva.

To pomeni, da trenutne uteži, kot so `0.50 / 0.30 / 0.20`, niso kanonična psihološka mera. So lahko samo implementacijski približek oziroma zgodovinski artefakt, ne pa vir resnice o odločanju.

### B. Situacija ne spreminja hierarhije

Strani 51-52, 63-64, 104, 145 in 164-165 jasno ločujejo:

- stalni značaj;
- trenutno razpoloženje;
- trenutno aktivnost posameznega razuma;
- začasno funkcionalno oslabelost;
- sodelovanje oziroma spor med razumi;
- začasno prepuščanje naloge kompetentnejšemu razumu.

Primer direktorja, ki zamuja v službo oziroma je odsoten, je posebej uporaben: pomočnik je lahko začasno pomembnejši za izvedbo naloge, vendar s tem ne postane direktor. Ko se direktor vrne, je hierarhija ista.

### C. Podrejeni razum lahko dobi nalogo, ne pa novega značajskega položaja

Dokument večkrat govori o prepuščanju nalog. Sprejemajoči razumi lahko kompetentnejšemu podrejenemu razumu prepustijo določeno opravilo. Primer Maleka pokaže Instinkt, ki med dirko Emociu dovoli, da izvede motorično nalogo.

To je treba modelirati kot:

- `task_delegation`;
- `operational_controller`;
- `processor_availability`;

in ne kot spremembo `character_authority`.

### D. Racio je edini neposredno zaveden in besedni razum

Na strani 43 je trditev formulirana zelo jasno: besede posluša samo Racio, Emocio in Instinkt pa opazujeta in zaznavata druge informacije.

Erosovi komentarji dodatno pravijo:

- vse, česar se zavestno zavedamo, je že v Racijevem svetu;
- tudi zavestna slika, občutek ali strah je Racijeva zaznava oziroma prevod;
- do Emocia in Instinkta nimamo neposrednega dostopa;
- argumenti v jeziku Racia za druga dva niso neposredna komunikacija.

Zato mora vsak tekstovni izhod Emocia ali Instinkta ostati označen kot **Racijev prevod hipotetičnega nezavednega signala**.

### E. Odločitev, vedenjski rezultat in spoznanje niso ista stvar

Strani 76-77 in 99 ločijo:

- zavestno Racijevo odločitev;
- vpliv nezavednih razumov na dejansko vedenje;
- spoznanje, do katerega po lastni poti pridejo vsi trije.

Spoznanje ni samo močna odločitev. Je stanje, ko vsi trije pridejo do istega sklepa in v človeku ni notranje sile, ki bi temu sklepu nasprotovala.

Sistem mora zato ločeno vrniti:

1. `mind_proposals`;
2. `conscious_decision`;
3. `predicted_behavior`;
4. `racio_narration`;
5. `spoznanje_status`.

### F. Značaj je pot do sklepa, ne vedenjski stereotip

Eros večkrat opozori, da:

- previdnost še ne dokazuje Instinkta;
- načrt še ne dokazuje Racia;
- smeh, spolnost, družabnost ali napad še ne dokazujejo Emocia;
- vsi razumi lahko navzven dosežejo enak rezultat po drugačni notranji poti.

To je neposreden razlog, da keyword classifier ali seznam pričakovanih vedenj ne sme biti glavni evaluator pravilnosti.

### G. Sprejemanje je odnos med razumi, ne “varen majhen korak”

Sprejemanje pomeni predvsem:

- medsebojno priznavanje;
- sodelovanje;
- manj popačenja drugih dveh;
- možnost prepuščanja nalog;
- manj sabotiranja;
- sposobnost živeti z drugačnim sklepom drugega razuma.

Sprejemajoči človek je lahko drzen, previden, hiter ali počasen. Reverzibilni pilot ni sam po sebi dokaz sprejemanja.

---

# 2. Glavni sklep za novo arhitekturo

Nova osrednja formula projekta naj bo:

```text
končni rezultat =
    stabilna ordinalna hierarhija značaja
  + tri neodvisne procesorske presoje
  + eksplicitno trenutno stanje sodelovanja
  + eksplicitna delegacija ali funkcionalna omejitev
  + Racijev zavestni prevod rezultata
```

Ne uporabljaj več formule:

```text
končni rezultat = weight * confidence + situational bonus
```

Situacija sme vplivati na:

- vsebino signala;
- intenzivnost;
- stopnjo negotovosti;
- aktivirani spomin ali cilj;
- telesni alarm;
- socialno sliko;
- količino konflikta.

Situacija ne sme sama od sebe spreminjati:

- stalnega vrstnega reda avtoritete;
- značajskega tipa;
- pravila odločanja.

---

## 2.1 Neposredna primerjava virov z aktualnim repozitorijem

Spodnja tabela je razlog, da samo nov prompt ali QLoRA adapter ne bosta zadostovala.

| Področje | Primarni viri | Aktualni repo | Potreben popravek |
|---|---|---|---|
| Narava značaja | Stabilna, ordinalna hierarhija; pomemben je vrstni red, ne velikost razlike | `profiles.py` uporablja kontinuirane uteži `0.50/0.30/0.20`, `0.40/0.40/0.20` | Uvedi `authority_tiers`; uteži označi kot legacy |
| Situacija | Aktivira vsebino, razpoloženje in intenzivnost; ne spreminja značaja | `_resultant_pressure` računa `weight * confidence` in situacijskemu driverju doda `+0.18` | Odstrani situacijski bonus iz odločanja |
| Procesorji | Vsak razum sam pride do sklepa; šele nato učinkuje hierarhija | `_llm_rei_signal` vsakemu procesorju pošlje profil in influence weights | Procesorji v controlled mode postanejo profilno slepi |
| Zaznavni vhod | Besede neposredno posluša Racio; E/I zaznavata druge modalnosti | Vsi trije prejmejo isti surovi tekst situacije | Uvedi `SceneFrame` in mind-specific input packets |
| Emocio in Instinkt | Njuna zavestna besedila so samo Racijev prevod | Repo to deklarativno pozna, vendar jima LLM vseeno daje format samostojnih verbalnih agentov | Ohraniti translation caveat in omejiti output na strukturiran prevedeni signal |
| Končna odločitev | Pri neenakih razumih odloči višji; pri 13. odloča vsaj 2 od 3 | `EgoResultant` LLM lahko določi `resultant_leader_under_pressure` in spremeni center | Deterministični arbitrator; LLM samo narrator |
| Dva vodilna razuma | Dva direktorja; izrazit konflikt in težje odločanje | Repo uporablja pair score, prag konflikta in kompromisne uteži | V v1: agreement ali eksplicitni unresolved top-pair conflict |
| Spoznanje | Isti sklep vseh treh po različnih poteh | Polje je predvsem opisno, ne formalno izračunano | Dodaj `spoznanje_status` iz treh frozen proposals |
| Sprejemanje | Kakovost odnosa in sodelovanja med razumi | `acceptance.py` uporablja keyworde in “bounded reversible action” hitro označi kot accepting | Sprejemanje naj bo eksplicitno stanje oziroma ločen classifier |
| Značaj in vedenje | Značaj je pot; isto vedenje ima lahko tri izvore | Eval scenariji in action classifier pogosto sklepajo iz površinskih besed | Kontrastne družine: same behavior/different route |
| Kanon | Trde trditve, Erosove razširitve in izpeljave morajo biti ločene | `processor_contracts.json` vsebuje benchmark-specific quit-job/runway pravila | Source-traceable canon v2 in ločen eval config |
| Jezik | Slovenski izvirnik je semantično najmočnejši; prevodi izgubljajo pomen | `rei_knowledge_index.json` in dataset manifest sta angleška; generator zahteva English | Slovenski kanon + angleški gloss + dvojezični eval |
| Dataset | Pot razmišljanja je pomembnejša od površinskega rezultata | Teacher model je v prvem pilotu zbližal vse procesorje v isto praktično rešitev | Ročno pregledan gold-mini pred treningom |
| QLoRA | Lahko izboljša jezik in procesorsko specializacijo | Repo še nima dejanskega reproducibilnega training pipelinea | Ločeni adapterji, HF/PEFT referenca, eval in šele nato Ollama |
| Aktivna dokumentacija | Baseline, orodja in eksperimenti morajo biti jasno ločeni | `CURRENT.md` še opisuje UI/API kot arhivirana, čeprav `app/gui` deluje kot aktiven workbench | Posodobi active boundary brez rušenja baselinea |

## 2.2 Kaj je v trenutnem repu vredno ohraniti

Refactor naj ne zavrže dobrih delov:

- ločenih Pydantic signalov za Racio, Emocio in Instinkt;
- `translated_by_racio` in `is_conscious` invariantov;
- source reference ideje;
- contract loaderja;
- repair in fallback diagnostike;
- 156-case infrastrukturnega runnerja kot legacy primerjave;
- GUI-ja za side-by-side pregled;
- `review_only` varovalke pri uvoženem matrix datasetu;
- hranjenja modela, prompta, tokenov in run artefaktov;
- arhiviranja prejšnjih pristopov namesto njihovega brisanja.

Nova pot naj te dele ponovno uporabi, ne pa ohrani napačne odločevalne logike samo zato, ker je okoli nje že veliko infrastrukture.

# 3. Ciljna hibridna arhitektura

## 3.1 Pregled toka

```text
RAW USER INPUT
      |
      v
NEUTRAL SCENE FRAME
      |
      +--------------------+--------------------+
      |                    |                    |
      v                    v                    v
RACIO INPUT PACKET   EMOCIO INPUT PACKET  INSTINKT INPUT PACKET
      |                    |                    |
      v                    v                    v
RACIO PROCESSOR      EMOCIO PROCESSOR      INSTINKT PROCESSOR
(LLM / adapter)      (LLM / adapter)        (LLM / adapter)
      |                    |                    |
      +--------------------+--------------------+
                           |
                           v
                 FROZEN MIND PROPOSALS
                           |
                           v
       CHARACTER AUTHORITY + DYNAMIC MIND STATE
                           |
                           v
             DETERMINISTIC ARBITRATION ENGINE
                           |
                           v
                    DECISION RESULTANT
                           |
                           v
             RACIO NARRATOR / VERBAL TRANSLATOR
                           |
                           v
                 USER-FACING EXPLANATION
```

## 3.2 Kaj je LLM-jevo in kaj ni

### LLM oziroma QLoRA naj dela:

- procesorsko specifično zaznavo in presojo;
- tvorjenje strukturiranega predloga posameznega razuma;
- omejeno razlago poti, po kateri je razum prišel do predloga;
- Racijev končni verbalni prikaz že izračunanega rezultata;
- slovenščino, angleščino in terminološko doslednost.

### Deterministična koda naj dela:

- razčlenitev 13 značajskih hierarhij;
- izbiro pravila odločanja;
- večino pri trinajstem značaju;
- spoštovanje enega ali dveh vodilnih razumov;
- ločitev avtoritete od trenutne aktivnosti;
- izračun agreement patterna;
- odločitev, ali je nastalo simulirano spoznanje;
- zaščito pred tem, da LLM spremeni profil ali izid;
- validacijo, da narrator ni prepisal rezultata.

### LLM ne sme več sam odločati:

- kateri razum je postal “resultant leader”;
- ali situacija prepiše značaj;
- kakšna je hierarhija;
- ali je prišlo do večine;
- ali je prišlo do spoznanja.

---

# 4. Nova podatkovna shema

Implementiraj novo shemo vzporedno z obstoječo v `app/backend/rei/models_v2.py`. Po stabilizaciji jo lahko prestaviš v `models.py`.

## 4.1 Osnovni tipi

```python
from typing import Literal
from pydantic import BaseModel, Field

MindId = Literal["R", "E", "I"]
LanguageCode = Literal["sl", "en"]
EvidenceMode = Literal[
    "explicit_text",
    "described_visual",
    "described_body_signal",
    "described_smell_or_taste",
    "inferred_from_context",
    "unknown",
]
```

## 4.2 Nevtralni opis situacije

```python
class SceneOption(BaseModel):
    id: str
    label_sl: str
    label_en: str = ""

class SceneEvidence(BaseModel):
    id: str
    text: str
    mode: EvidenceMode
    confidence: float = Field(ge=0, le=1)
    explicit: bool = True

class SceneFrame(BaseModel):
    scenario_id: str
    language: LanguageCode
    raw_text: str
    actors: list[str]
    facts: list[SceneEvidence]
    options: list[SceneOption]
    explicit_goals: list[str]
    constraints: list[str]
    social_cues: list[SceneEvidence]
    visual_cues: list[SceneEvidence]
    body_cues: list[SceneEvidence]
    trust_and_boundary_cues: list[SceneEvidence]
    time_and_number_cues: list[SceneEvidence]
    unknowns: list[str]
```

Pomembno: `SceneFrame` naj ne določa, kateri razum je “pravilen”. Samo normalizira opis.

## 4.3 Svet posameznika

Samo značaj ni dovolj za napoved konkretne odločitve. Viri poudarjajo, da je rezultat odvisen od vsebine posameznikovega sveta in izkušenj.

```python
class MindWorldContext(BaseModel):
    mind: MindId
    learned_associations: list[str] = []
    active_goals: list[str] = []
    unresolved_losses_or_images: list[str] = []
    trusted_patterns: list[str] = []
    rejected_patterns: list[str] = []
    known_memories: list[str] = []
    source: Literal["user_supplied", "synthetic_fixture", "unknown"] = "unknown"

class PersonWorldState(BaseModel):
    racio: MindWorldContext
    emocio: MindWorldContext
    instinkt: MindWorldContext
```

V prvi verziji je ta kontekst lahko prazen. Sistem mora takrat jasno povedati, da simulira splošni procesorski odziv, ne specifične osebe.

## 4.4 Procesorski vhod

```python
class MindInputPacket(BaseModel):
    mind: MindId
    scene_id: str
    accepted_evidence_ids: list[str]
    translated_evidence_ids: list[str]
    excluded_evidence_ids: list[str]
    world_context: MindWorldContext
    caveat: str
```

### Usmerjanje

Racio packet:

- besede;
- številke;
- čas;
- eksplicitne možnosti;
- posledice;
- pravila;
- uporabnost;
- neznanke.

Emocio packet:

- opisani prizori;
- obrazi, vidnost in socialni odziv;
- sedanja, želena in porušena slika;
- pripadnost;
- občudovanje ali ponižanje;
- tekmovanje;
- privlačnost in odboj;
- gibanje in neposredna izkušnja.

Instinkt packet:

- nevarnost;
- izguba;
- meja;
- zaupanje;
- navezanost;
- pomanjkanje;
- telesni alarm;
- opisani vonj, okus, bolečina, temperatura;
- neznana sprememba.

Ker je vstop uporabnika besedilen, naj bo pri Emociu in Instinktu vedno zapisano, da gre za **Racijev opis prizora oziroma občutka**, ne za neposredno zaznavo.

## 4.5 Predlog posameznega razuma

```python
DecisionClass = Literal[
    "approach",
    "withdraw",
    "attack",
    "delay",
    "analyze",
    "protect",
    "maintain",
    "change",
    "disclose",
    "conceal",
    "negotiate",
    "delegate",
    "unknown",
]

class MindProposal(BaseModel):
    schema_version: Literal["rei-mind-proposal-v2"] = "rei-mind-proposal-v2"
    mind: MindId
    source_language: LanguageCode
    translated_by_racio: bool
    option_id: str | None
    decision_class: DecisionClass
    route_tags: list[str]
    motive_tags: list[str]
    concern_tags: list[str]
    accepted_evidence_ids: list[str]
    ignored_or_rejected_evidence_ids: list[str]
    proposal_text: str
    objection_text: str
    confidence: float = Field(ge=0, le=1)
    missing_information: list[str]
    uncertainty: str
```

`route_tags` naj bodo kratke, kanonično določene oznake, ne dolga veriga notranjega razmišljanja.

Primeri:

Racio:

- `FACT_UNKNOWN_SPLIT`
- `UTILITY_COMPARISON`
- `TIME_SEQUENCE`
- `CONTROL_AND_EXECUTION`
- `RATIONALIZATION_RISK`

Emocio:

- `CURRENT_IMAGE`
- `DESIRED_IMAGE`
- `BROKEN_IMAGE`
- `RECOGNITION_OR_SHAME`
- `ATTRACTION_OR_REJECTION`
- `COMPETITION`

Instinkt:

- `THREAT_SCAN`
- `LOSS_SCAN`
- `TRUST_TEST`
- `BOUNDARY_CHECK`
- `ATTACHMENT_PROTECTION`
- `SCARCITY`
- `BODY_ALARM`
- `FLIGHT_OR_CLOSURE`

## 4.6 Značajska avtoriteta brez decimalnih uteži

```python
DecisionRule = Literal[
    "single_leader",
    "ordered_leader",
    "joint_leadership",
    "two_of_three",
]

class CharacterAuthority(BaseModel):
    profile_id: str
    authority_tiers: list[list[MindId]]
    decision_rule: DecisionRule
```

Primeri:

```python
R      = [["R"], ["E", "I"]]
R_E_I  = [["R"], ["E"], ["I"]]
RE     = [["R", "E"], ["I"]]
REI    = [["R", "E", "I"]]
```

Decimalne vrednosti lahko začasno ostanejo samo v legacy poljih za prikaz starih poročil. Nova arbitraža jih ne sme uporabljati.

## 4.7 Dinamično stanje

```python
class ProcessorAvailability(BaseModel):
    R: float = Field(default=1.0, ge=0, le=1)
    E: float = Field(default=1.0, ge=0, le=1)
    I: float = Field(default=1.0, ge=0, le=1)

class TaskDelegation(BaseModel):
    enabled: bool = False
    delegated_by: MindId | None = None
    delegated_to: MindId | None = None
    task_scope: str = ""
    reason: str = ""

class AcceptanceStateV2(BaseModel):
    mode: Literal["accepting", "non_accepting", "mixed", "unknown"] = "unknown"
    mutual_recognition: float = Field(default=0.5, ge=0, le=1)
    cooperation: float = Field(default=0.5, ge=0, le=1)
    suppression: dict[MindId, float]
    pair_conflict: dict[str, float]
    sabotage_risk: dict[MindId, float]
    notes: list[str] = []

class DynamicMindStateV2(BaseModel):
    acceptance: AcceptanceStateV2
    availability: ProcessorAvailability
    delegation: TaskDelegation
    acute_operational_override: MindId | None = None
    acute_override_reason: str = ""
```

`acute_operational_override` ne pomeni spremembe značaja. Uporabi se samo pri eksplicitno modelirani funkcionalni oslabelosti, substanci, poškodbi, spanju, izredni delegaciji ali podobnem scenariju. Ne aktiviraj ga na podlagi besede “strah”, “tveganje” ali “vidnost”.

## 4.8 Končni rezultat

```python
AgreementPattern = Literal[
    "all_three_same",
    "two_same_one_different",
    "all_different",
    "top_pair_same",
    "top_pair_conflict",
    "unknown",
]

SpoznanjeStatus = Literal[
    "simulated_spoznanje",
    "partial_agreement",
    "no_spoznanje",
    "unknown",
]

class DecisionResultant(BaseModel):
    schema_version: Literal["rei-decision-resultant-v2"] = "rei-decision-resultant-v2"

    profile_id: str
    authority_tiers: list[list[MindId]]
    decision_rule: DecisionRule

    mind_proposals: dict[MindId, MindProposal]
    agreement_pattern: AgreementPattern
    spoznanje_status: SpoznanjeStatus

    decision_source_minds: list[MindId]
    selected_option_id: str | None
    selected_decision_class: DecisionClass
    unresolved: bool
    unresolved_reason: str

    structural_authority_leaders: list[MindId]
    operational_controller: MindId | None
    task_delegation: TaskDelegation

    acknowledged_objections: dict[MindId, str]
    suppressed_or_distorted_signals: list[MindId]

    conscious_decision: str
    predicted_behavior: str
    racio_narration_origin: Literal[
        "racio_own_conclusion",
        "translation_of_emocio",
        "translation_of_instinkt",
        "translation_of_joint_leadership",
        "translation_of_majority",
        "unclear",
    ]
    racio_narration: str

    acceptance_state: AcceptanceStateV2
    uncertainty: str
    safety_flags: list[str]
```

Začasno ohrani `ego_resultant` kot compatibility alias, vendar naj nova notranja koda uporablja `DecisionResultant`. Ne uvajaj novega “Ego agenta”.

---

# 5. Deterministična arbitraža

Ustvari:

```text
app/backend/rei/arbitration.py
```

## 5.1 Osnovni algoritem

```python
def arbitrate(
    authority: CharacterAuthority,
    proposals: dict[MindId, MindProposal],
    state: DynamicMindStateV2,
) -> DecisionResultant:
    # 1. normaliziraj glasove po option_id oziroma decision_class
    # 2. izračunaj agreement pattern
    # 3. preveri all-three convergence
    # 4. uporabi ordinalno pravilo profila
    # 5. ločeno določi operational controller
    # 6. uporabi acceptance samo za sodelovanje, priznanje ugovorov in sabotage
    # 7. sestavi rezultat brez LLM odločanja
```

## 5.2 Pravila za profile z enim vodilnim razumom

Profili:

- `R>(E=I)`
- `E>(R=I)`
- `I>(R=E)`

Pravilo:

1. vodilni razum določi odločitev;
2. podrejena razuma ne moreta samodejno prevzeti avtoritete;
3. njuna ugovora morata ostati vidna;
4. pri sprejemanju vodilni razum lahko prilagodi način izvedbe ali preda nalogo;
5. pri nesprejemanju ju lahko popači, ignorira ali racionalizira;
6. situacijska intenzivnost sama ne spremeni odločevalca.

## 5.3 Pravila za tristopenjske profile

Profili:

- `R>E>I`
- `R>I>E`
- `E>R>I`
- `E>I>R`
- `I>R>E`
- `I>E>R`

Pravilo:

1. prvi tier ima odločevalno avtoriteto;
2. drugi tier ima večjo korekcijsko oziroma izvedbeno težo kot tretji;
3. tretji ostane prisoten kot ugovor, cena ali prezrt signal;
4. noben decimalni bonus ne sme prehiteti prvega tiera;
5. če je prvi razum funkcionalno nedosegljiv ali eksplicitno delegira nalogo, se lahko `operational_controller` spremeni, `structural_authority_leaders` pa ostane isti.

## 5.4 Pravila za parne značaje

Profili:

- `(R=E)>I`
- `(R=I)>E`
- `(E=I)>R`

Viri jasno podpirajo dva enakovredna direktorja in značilno težje odločanje, ne dajejo pa dovolj jasnega univerzalnega pravila, kaj se zgodi pri vsakem njunem nesoglasju.

Zato v v1 naredi konservativno:

1. če se vodilna razuma strinjata, njuna odločitev zmaga;
2. če se ne strinjata:
   - rezultat je `unresolved=True`;
   - agreement je `top_pair_conflict`;
   - podrejeni razum ne sme avtomatsko postati tie-breaker;
   - stanje lahko kaže nihanje, zastoj, izmenični pritisk ali sabotiranje;
3. če je prisotna eksplicitna delegacija ali funkcionalna nedosegljivost enega od vodilnih, lahko drugi začasno vodi nalogo;
4. kasneje lahko dodaš dodatno pravilo samo, če ga podpre nov kanonični vir ali dobro označen Erosov primer.

To odprto vprašanje zapiši v `knowledge/canon/open_questions_v2.md`.

## 5.5 Trinajsti značaj

Profil:

- `R=E=I`

Pravilo:

1. če dva izbereta isto možnost, ta dobi večino;
2. tretji je preglasovan, ne izbrisan;
3. če vsi izberejo drugače, rezultat ostane nerešen;
4. če vsi trije pridejo do istega sklepa, označi `simulated_spoznanje`;
5. Racio nima prednosti samo zato, ker je verbalni.

## 5.6 Spoznanje

V v1:

```python
spoznanje = (
    all_three_have_same_option
    and all_three_have_independent_route_tags
)
```

Ne poimenuj tega objektivna resnica. Uporabi izraz `simulated_spoznanje`, ker sistem simulira notranjo konvergenco, ne dokazuje resničnosti sklepa.

## 5.7 Zavestna odločitev in dejansko vedenje

Pri profilih z vodilnim Emociem ali Instinktom:

- `decision_source_minds` lahko vsebuje `E` oziroma `I`;
- `conscious_decision` in `racio_narration` sta vseeno Racijev prevod;
- `racio_narration_origin` mora to jasno pokazati.

Pri konfliktu lahko `conscious_decision` in `predicted_behavior` odstopata. Tega ne napoveduj s prostim ugibanjem. Odstopanje uporabi samo, ko ga podpira eksplicitni `AcceptanceStateV2`, sabotage fixture ali jasno označen primer.

---

# 6. Profilno slepi procesorji

## 6.1 Obvezna sprememba

Iz procesorskih payloadov odstrani:

- `character_profile`;
- `influence_weights`;
- `character_definition`;
- `coalition_rules`;
- `decision_threshold`.

Spremeni:

```text
app/backend/rei/engine.py
app/backend/rei/contract_loader.py
app/backend/rei/knowledge.py
app/gui/server.py
```

Procesor mora dobiti:

- `MindInputPacket`;
- svoj kanon;
- opcijski `MindWorldContext`;
- želeni izhodni jezik;
- seznam razpoložljivih možnosti.

Profil dobi šele arbitrator.

## 6.2 Zakaj je to potrebno

Če Instinktu pred odgovorom poveš, da je tretji, ne meriš več njegove neodvisne presoje. Meriš njegovo vedenje v že znani hierarhiji.

Za realističen model osebe lahko profil dolgoročno vpliva na to, kakšen svet se je nabral v posameznem razumu. To pa naj bo izraženo v `PersonWorldState`, ne v trenutnem procesorskem promptu.

Tako ločimo dve raziskovalni nalogi:

### Controlled profile matrix

Isti trije zamrznjeni predlogi se uporabijo za vseh 13 profilov. To meri učinek hierarhije.

### Person-world simulation

Profil je skozi zgodovino vplival na razvoj sveta. Razlike se vnašajo kot eksplicitni `MindWorldContext`. To meri osebo, ne samo abstrakten značaj.

## 6.3 Test

Dodaj:

```text
tests/v2/test_processor_profile_blindness.py
```

Za isti `SceneFrame`, isti `MindWorldContext`, isti model, seed in parametre:

- procesorski payload ne sme vsebovati profila;
- option ID in route tags morajo biti enaki ne glede na profil, ki bo uporabljen kasneje;
- tekstovna variacija je dovoljena samo, če ne spremeni semantičnega predloga.

---

# 7. Odstranitev trenutnega situacijskega overridea

Odstrani iz nove poti:

```python
pressure[mind] = profile_weight * confidence
pressure[situational_driver] += 0.18
```

Odstrani tudi keyword-driven avtoriteto iz `_situational_driver`.

Keyword sistem lahko ostane samo kot:

- diagnostični signal;
- predlog za `SceneFrame`;
- opozorilo, katere vrste podatkov so prisotne.

Nikoli ne sme neposredno določiti odločujočega razuma.

Dodaj test:

```text
tests/v2/test_situation_never_changes_structural_rank.py
```

Primeri:

- R-vodilni profil v zelo strašljivi situaciji ostane R-vodilni;
- I-vodilni profil v tehničnem problemu ostane I-vodilni;
- E-vodilni profil v finančnem problemu ostane E-vodilni;
- pri vseh treh se vsebina predlogov spremeni, avtoriteta pa ne.

---

# 8. Odstranitev benchmarkskih pravil iz kanona

Trenutni `knowledge/canon/processor_contracts.json` vsebuje pravila, kot so:

- “first business-change scenario”;
- quit-job;
- runway;
- side venture;
- revenue milestone;
- all-in transition.

To niso kanonične lastnosti Racia, Emocia ali Instinkta. To so popravki določenega eval scenarija.

## 8.1 Nova razdelitev

Ustvari:

```text
knowledge/canon/claims_v2.jsonl
knowledge/canon/processors_v2.yaml
knowledge/canon/character_rules_v2.yaml
knowledge/canon/open_questions_v2.md
knowledge/glossary/rei_terms_v2.yaml
knowledge/evals/scenario_expectations_v2.yaml
```

### `claims_v2.jsonl`

Vsaka vrstica:

```json
{
  "claim_id": "C-CHAR-002",
  "status": "direct_source",
  "kind": "EK",
  "scope": "character_arbitration",
  "sl": "Pri neenakih razumih odloči močnejši; velikost razlike ni odločilna.",
  "en_gloss": "With unequal minds, the higher-ranked mind decides; the size of the gap is not decisive.",
  "source_file": "Docs/Eros - pogovori.pdf",
  "page": 88,
  "translation_notes": "Močnejši pomeni višje v značajski hierarhiji, ne trenutno glasnejši.",
  "risk_class": "core"
}
```

### Statusi

- `direct_source`
- `source_synthesis`
- `implementation_hypothesis`
- `open_question`
- `deprecated_hypothesis`

`weighted_synthesis_working_note.md` označi kot:

```text
deprecated_hypothesis / superseded by direct source review 2026-07-10
```

Ne briši ga. Premakni ga v arhiv ali mu dodaj jasen status na vrh.

## 8.2 Začetni obvezni claimi

Vnesi najmanj:

- stabilnost značaja;
- ordinalna hierarhija;
- velikost razlike ni odločilna;
- en vodilni razum odloča;
- 13. značaj uporablja dva od treh;
- podrejeni lahko dobi nalogo;
- trenutna aktivnost ni sprememba značaja;
- samo Racio neposredno posluša besede;
- Emocio in Instinkt nista neposredno zavestna;
- zavestna odločitev poteka skozi Racia;
- spoznanje zahteva sklep vseh treh;
- sprejemanje izboljša sodelovanje;
- značaj je pot procesiranja, ne vedenjski rezultat;
- isto vedenje lahko izvira iz različnih razumov;
- slovenščina je semantični izvorni jezik projekta.

---

# 9. Dvojezični model brez izgube slovenskega jedra

## 9.1 Temeljno pravilo

**Slovenščina je kanonični semantični vir. Angleščina je operativni gloss za model.**

Ne naredi angleškega kanona in nato slovenskega prevoda. Naredi:

```text
slovenska trditev -> angleški operativni gloss -> povratni pregled v slovenščini
```

## 9.2 Rezervirani izrazi

V angleških promptih in datasetih ohrani naslednje termine nespremenjene:

- `Racio`
- `Emocio`
- `Instinkt`
- `razum`
- `značaj`
- `svet`
- `sprejemanje`
- `nesprejemanje`
- `spoznanje`
- `kulisa`
- `vodilni razum`
- `vzporedna razuma`

Vsak naj ima:

- `term_id`;
- slovensko definicijo;
- angleški gloss;
- prepovedane oziroma zavajajoče prevode;
- primer pravilne uporabe;
- opombo, kje se pomen razlikuje od vsakdanje rabe.

Primer:

```yaml
- term_id: REI_SPOZNANJE
  canonical_sl: spoznanje
  en_gloss: all-three internal convergence on the same conclusion
  do_not_translate_as:
    - realization
    - insight
    - revelation
  note: >
    English words may be used in prose, but the canonical REI state remains
    named spoznanje and requires all three minds to converge independently.
```

## 9.3 Jezikovni način runtimea

Dodaj:

```python
output_language: Literal["sl", "en"] = "sl"
canon_language: Literal["sl"] = "sl"
instruction_language: Literal["en", "sl", "mixed"] = "mixed"
```

Priporočena prva nastavitev:

- sistemska navodila: kratka angleščina;
- kanonične definicije: slovenščina + angleški gloss;
- JSON ključi: angleščina;
- uporabniški izhod: slovenščina;
- REI termini: slovenščina.

## 9.4 Dataset jezikovna mešanica

Ne zakleni manifest na `Literal["en"]`.

Dovoli:

```python
language: Literal["sl", "en", "mixed"]
source_language: Literal["sl", "en"]
```

Prvi eksperiment naj primerja dve mešanici:

### Mix A

- 70 % slovenskih primerov;
- 20 % angleških gloss primerov;
- 10 % poravnanih dvojezičnih primerov.

### Mix B

- 50 % slovenskih primerov;
- 40 % angleških gloss primerov;
- 10 % poravnanih dvojezičnih primerov.

Izberi po eval rezultatih, ne po občutku.

## 9.5 Dvojezični eval

Isti scenario family mora vsebovati:

- slovensko izvirno verzijo;
- angleški semantični gloss;
- slovensko parafrazo;
- angleško parafrazo.

Pri vseh štirih mora model obdržati:

- isti `option_id`;
- isti `decision_class`;
- iste bistvene route tags;
- enako zaznano negotovost v smiselni toleranci.

Ne meri prevoda z BLEU. Meri semantično ohranitev REI strukture.

---

# 10. Dataset v2

## 10.1 Ne uporabljaj več “model generated = gold”

Trenutni nedokončani dataset je pravilno ustavljen, ker so se vsi procesorji zbližali v runway, side-hustle in expense-audit odgovor.

Ne rešuj tega tako, da:

- v prompt napišeš pričakovani odgovor;
- z regexom prepišeš output;
- dodaš scenarijsko specifično pravilo;
- avtomatsko označiš veljaven JSON kot dober primer.

QLoRA bo sicer samo utrdil napako teacher modela.

## 10.2 Ločeni dataseti

Ustvari:

```text
datasets/rei_processor_gold_v2/
datasets/rei_arbitration_fixtures_v2/
datasets/rei_narration_gold_v2/
datasets/rei_bilingual_alignment_v2/
datasets/rei_adversarial_eval_v2/
```

### `rei_processor_gold_v2`

Človeško pregledani R, E in I predlogi.

### `rei_arbitration_fixtures_v2`

Deterministične vhodno-izhodne tabele za vseh 13 profilov. Te niso namenjene učenju LLM-ja, ampak testiranju kode.

### `rei_narration_gold_v2`

Primeri, kako Racio ubesedi že izračunan rezultat, ne da bi ga spremenil.

### `rei_bilingual_alignment_v2`

Poravnani slovensko-angleški primeri.

### `rei_adversarial_eval_v2`

Nikoli ne gre v train. Vsebuje keyword traps, parafraze in nasprotujoče površinske znake.

## 10.3 Scenario family

Nova osnovna enota ni primer, ampak družina:

```json
{
  "scenario_family_id": "career_transition_001",
  "variants": [
    "sl_neutral",
    "en_neutral",
    "sl_paraphrase",
    "en_paraphrase",
    "sl_keyword_trap",
    "same_behavior_different_motive"
  ]
}
```

Vsi prevodi, parafraze, profili in state variants iste družine morajo biti v istem splitu.

## 10.4 Kontrastni primeri

Vsaka pomembna kategorija naj vsebuje:

### A. Isto vedenje, druga pot

Primer: oseba ne gre na sestanek.

- Racio: sestanek nima uporabnosti ali podatkovne vrednosti;
- Emocio: prizor je ponižujoč, dolgočasen ali statusno mrtev;
- Instinkt: izpostavljenost, meja ali nevarnost izgube.

### B. Isti motiv, druga vedenja

Primer Instinktove zaščite lahko vodi v:

- umik;
- postavitev meje;
- ohranitev obstoječega;
- iskanje pomoči;
- napad samo, če je stisnjen v kot.

### C. Zavajajoče besede

Besedilo vsebuje “plan”, vendar odločitev izvira iz Instinktove izločitvene poti.

Besedilo vsebuje “strah”, vendar gre lahko za Emocijevo jezo zaradi prisilne situacije.

Besedilo vsebuje “sliko”, vendar je to Racijev tehnični diagram.

### D. Isti značaj, drugačen svet

Isti profil in ista situacija, toda različni `MindWorldContext` vodijo v različne predloge. To prepreči stereotip “R vedno naredi X”.

### E. Isti procesorski bundle, 13 profilov

Trije predlogi se zamrznejo. Nato se izvede vseh 13 arbitraž. To je glavni test karakterne kavzalnosti.

## 10.5 Velikost prvih datasetov

### Gold-mini, preden se sploh zažene QLoRA

- 48 scenario families;
- 3 ročno pregledani procesorski predlogi na family;
- najmanj 144 procesorskih gold primerov;
- vseh 13 arbitraž za vsako family;
- 20 posebej težkih dvojezičnih variant;
- 20 keyword-trap variant.

To ni končni trening set. To je dokaz, da so schema, review UI in evali pravilni.

### Gold-v1

Cilj po uspešnem gold-mini:

- 200-300 scenario families;
- 600-900 izvornih procesorskih gold primerov;
- z jezikovnimi in kontrastnimi variantami približno 2.000-4.000 trening primerov;
- najmanj 300 popolnoma ločenih eval primerov;
- uravnoteženost po razumih, route tags, decision classes in jezikih.

Kakovost ima prednost pred količino.

## 10.6 Review statusi

Zamenjaj en sam `valid` z ločenimi statusi:

```text
schema_valid
canon_reviewed
route_reviewed
language_reviewed
behavior_reviewed
training_approved
rejected
```

Primer je primeren za trening samo, če je `training_approved=True`.

## 10.7 Review checklist za procesor

### Racio

- loči dejstva in neznanke;
- uporablja besede, številke, čas, korist, posledice;
- ne prevzame telesnega alarma kot lastno native zaznavo;
- ne postane avtomatsko previden;
- ne uporabi Emocijeve slike kot glavni razlog;
- zazna možnost racionalizacije;
- njegov zaključek ni samo slogovno “suh”, ampak izhaja po Racijevi poti.

### Emocio

- gradi prizor oziroma sliko;
- loči sedanjo, želeno in porušeno sliko;
- vidi pozornost, pripadnost, privlačnost, tekmovanje ali ponižanje;
- ne dela budgeta, runwaya ali risk matrixa;
- ni generični empat;
- lahko je sprejemajoč ali nesprejemajoč;
- njegov predlog je Racijev prevod, ne literalni notranji govor.

### Instinkt

- pregleda nevarnost, izgubo, mejo, zaupanje, navezanost ali pomanjkanje;
- ne uporablja poslovne optimizacije;
- ni samo generični pesimist;
- razlikuje zaščito od panike;
- ne prevzame statusne slike kot glavni razlog;
- njegov predlog je Racijev prevod.

---

# 11. Process trace brez učenja skrite verige razmišljanja

Trenutni dataset zahteva precej prosto `process_trace`. To zamenjaj s kratkim, opazljivim dokazom poti:

```json
{
  "route_evidence": {
    "accepted_evidence_ids": ["ev-2", "ev-5"],
    "route_tags": ["THREAT_SCAN", "BOUNDARY_CHECK"],
    "decision_bridge": "Nejasna meja in možnost nepovratne izgube vodita v zaščitni predlog."
  }
}
```

Ne treniraj dolgih notranjih monologov oziroma chain-of-thoughta. Za SFT zadostujejo:

- route tags;
- izbrane evidence IDs;
- kratek decision bridge;
- končni strukturirani predlog.

---

# 12. Eval v2

Ustvari:

```text
app/backend/rei/eval_v2.py
scripts/run_rei_eval_v2.py
tests/v2/
```

## 12.1 Strukturne metrike

- JSON parse rate;
- required keys;
- enum validity;
- forbidden extra keys;
- option ID validity;
- source language;
- adapter/base metadata.

## 12.2 Procesorska identiteta

- profile blindness;
- route tag precision;
- borrowed-channel violations;
- decision-class confusion matrix;
- blind human identity test;
- semantic distinctness, ne samo Jaccard besed.

## 12.3 Karakterna kavzalnost

Na istem bundleu:

- pravilna authority tier;
- pravilno decision rule;
- 0 situacijskih sprememb strukturnega vodje;
- pravilna 2-of-3 večina;
- pravilno unresolved stanje pri treh različnih glasovih;
- pravilen top-pair conflict;
- pravilno ločena delegacija;
- pravilen operational controller;
- pravilen simulated spoznanje.

## 12.4 Jezik

- slovensko-angleška semantična konsistentnost;
- dosledna uporaba rezerviranih izrazov;
- brez pretvarjanja `razum` v ordinary “reason”;
- brez enačenja `spoznanje` z navadnim “insight”;
- slovnična in terminološka kakovost;
- isti option ID čez prevode.

## 12.5 Robustnost

- parafraza;
- keyword trap;
- negacija;
- dolga nerelevantna vsebina;
- zamenjan vrstni red informacij;
- dvoumna situacija;
- manjka možnost;
- ista zunanja akcija, drugačen notranji motiv.

## 12.6 Neodvisnost evaluatorja

Evaluator ne sme samo preverjati, ali output vsebuje besede iz prompta.

Gold primer naj vsebuje:

- route tags;
- evidence IDs;
- option ID;
- canonical rationale labels.

Besedna podobnost je lahko diagnostična, ne glavna ocena.

## 12.7 Začetni prehodi

Pred QLoRA:

- 100 % arbitražnih truth-table testov;
- 0 profile leakage v procesorske payloade;
- 0 situational authority overrideov;
- 100 % narrator immutability testov;
- najmanj 85 % pravilna identifikacija procesorja v blind reviewu na gold-mini;
- najmanj 90 % semantična skladnost SL/EN pri option ID in route tags.

Po QLoRA:

- najmanj 99 % schema-valid output;
- 0 identity flag violations;
- merljivo boljši blind processor identification od base modela;
- najmanj 50 % manj trenutnih missing-key oziroma format failures;
- brez poslabšanja na ne-REI splošnih sanity testih;
- brez večjega action collapsea.

Pragovi so projektni quality gates in jih je dovoljeno prilagoditi samo z zapisanim razlogom, ne zato, da bi test “šel skozi”.

---

# 13. QLoRA strategija

## 13.1 Ne treniraj arbitraže

Arbitration engine je determinističen. Ne izdeluj `EgoResultant QLoRA` adapterja v prvi verziji.

QLoRA uporabi za:

1. Racio processor;
2. Emocio processor;
3. Instinkt processor;
4. kasneje opcijsko Racio narrator.

## 13.2 Najprej trije ločeni adapterji

Prvi poskus:

```text
rei-racio-v1
rei-emocio-v1
rei-instinkt-v1
```

Vsi uporabljajo isti base model in isti tokenizer, vendar vsak svoj dataset.

Razlog:

- trenutna glavna težava je konvergenca;
- ločeni adapterji zmanjšajo role bleed;
- vsak adapter lahko dobi drugačno učno distribucijo;
- eval je jasnejši;
- lažje odkrijemo, kateri razum potrebuje boljši kanon.

Šele ko vsi trije ločeno dosežejo quality gate, preizkusi en skupni multi-role adapter:

```text
rei-processors-shared-v1
```

Ta mora imeti močan target marker in popolnoma uravnotežen dataset. Če se role bleed poveča, ostani pri ločenih adapterjih.

## 13.3 Base model

Ne treniraj neposredno Ollama GGUF modela. QLoRA source of truth naj bo originalni Hugging Face model v Safetensors obliki z natančno določeno revizijo.

Codex naj naredi `training/model_registry.yaml`:

```yaml
models:
  - id: candidate-a
    hf_model_id: ...
    revision: ...
    architecture: ...
    tokenizer_revision: ...
    license: ...
    parameter_count: ...
    supports_bf16: ...
    json_baseline_score: ...
    slovenian_baseline_score: ...
    adapter_runtime:
      transformers_peft: true
      ollama_direct: unknown
      merged_gguf: pending
```

Izbor base modela naj temelji na:

- slovenski jezikovni kakovosti;
- JSON poslušnosti;
- licenčnih pogojih;
- PEFT kompatibilnosti;
- zmožnosti delovanja na dejanski strojni opremi;
- stabilnem chat templatu;
- možnosti izvoza.

Najprej preveri 7B-14B razred, ker bo razvojni krog bistveno hitrejši. 26B-35B poskusi šele, ko je pipeline dokazan in `hardware_probe.py` potrdi dovolj VRAM za izbrani sequence length, batch in optimizer.

## 13.4 Priporočena QLoRA osnova

Za začetni grid:

```yaml
quantization:
  load_in_4bit: true
  quant_type: nf4
  double_quant: true
  compute_dtype: bfloat16_if_supported_else_float16

lora:
  target_modules: all-linear
  r: [16, 32]
  alpha: [32, 64]
  dropout: 0.05
  bias: none
  task_type: CAUSAL_LM

training:
  learning_rate: [5e-5, 1e-4, 2e-4]
  epochs: [1, 2, 3]
  max_length: [2048, 4096]
  gradient_checkpointing: true
  assistant_only_loss: true
  packing: false_for_first_experiment
  seed: 42
```

To je grid, ne končna resnica. Izberi po evalih.

Hugging Face PEFT trenutno dokumentira klasičen QLoRA tok:

- 4-bit load;
- NF4;
- double quant;
- bfloat16 compute, kadar je podprt;
- `prepare_model_for_kbit_training`;
- LoRA na linearnih plasteh.

TRL podpira trening samo na assistant delu oziroma completion delu. To je primerno za naš strukturirani JSON output.

## 13.5 Trening skripte

Ustvari:

```text
training/
  README.md
  requirements.in
  requirements.lock
  model_registry.yaml
  configs/
    racio_v1.yaml
    emocio_v1.yaml
    instinkt_v1.yaml
    narrator_v1.yaml
  train_qlora.py
  evaluate_adapter.py
  compare_base_adapter.py
  merge_adapter.py
  export_ollama.py
  hardware_probe.py
  smoke_test_training.py
```

CLI primer:

```powershell
python training\hardware_probe.py

python training\train_qlora.py `
  --config training\configs\racio_v1.yaml `
  --dataset datasets\rei_processor_gold_v2\exports\racio

python training\evaluate_adapter.py `
  --adapter output\adapters\rei-racio-v1 `
  --eval-dataset datasets\rei_adversarial_eval_v2
```

## 13.6 Obvezni metadata

Vsak adapter mora vsebovati:

```json
{
  "adapter_id": "rei-racio-v1",
  "base_model_id": "...",
  "base_revision": "...",
  "tokenizer_hash": "...",
  "chat_template_hash": "...",
  "dataset_id": "rei_processor_gold_v2",
  "dataset_hash": "...",
  "target_mind": "R",
  "language_mix": {"sl": 0.7, "en": 0.2, "mixed": 0.1},
  "training_config_hash": "...",
  "git_commit": "...",
  "created_at": "..."
}
```

Ne dovoli nalaganja adapterja na drug base revision brez eksplicitnega overridea in opozorila.

## 13.7 Early stopping

Ne uporabljaj samo eval loss.

Stop oziroma izbor checkpointa naj upošteva:

- schema validity;
- processor identity;
- route accuracy;
- language consistency;
- action-class diversity;
- adversarial robustness;
- stock phrase repetition;
- base-vs-adapter delta.

## 13.8 Ollama deployment

Razvojni source of truth naj bo najprej `Transformers + PEFT`.

Dodaj nov provider:

```text
app/backend/rei/providers_peft.py
```

Ta naj zna:

- naložiti base model;
- naložiti izbrani adapter;
- preklapljati med tremi adapterji;
- izvajati isti JSON contract;
- zbirati enake diagnostics kot Ollama.

Ollama naj bo deployment target, ne edini development runtime.

Ollama Modelfile podpira `ADAPTER`, vendar zahteva natančno isti base model, na katerem je bil adapter treniran. Uradna dokumentacija trenutno navaja omejen seznam neposredno podprtih Safetensors adapter arhitektur. Zato ne predpostavljaj, da bo trenutni Qwen ali novejši Gemma adapter neposredno deloval.

Implementiraj tri export poti:

1. `transformers_peft` - referenčna eval pot;
2. `ollama_direct_adapter` - samo če je arhitektura potrjeno podprta;
3. `merged_model_to_gguf` - fallback po uspešnem mergeu adapterja.

Po izvozu vedno zaženi parity eval. Izvoz je sprejet samo, če izbrani option ID, route tags in odločilni tekst ostanejo primerljivi s PEFT referenco.

---

# 14. GUI spremembe

Sedanji workbench je uporabna osnova. Preoblikuj ga tako, da arhitektura postane vidna.

## 14.1 Processor panel

Prikazuje:

- `SceneFrame`;
- tri `MindInputPacket`;
- tri procesorske izhode;
- profil ni prikazan in se ne pošilja procesorjem;
- base vs adapter diff;
- jezikovni način;
- route tags;
- evidence IDs;
- schema in canon flags.

## 14.2 Arbitration panel

Šele tukaj uporabnik izbere:

- profil;
- acceptance state;
- availability;
- delegation;
- opcijski person-world state.

Nato panel pokaže:

- authority tiers;
- mind votes;
- agreement pattern;
- decision rule;
- selected option;
- structural leader;
- operational controller;
- simulated spoznanje;
- ugovore;
- Racijev narrator.

## 14.3 Dataset review panel

Dodaj filtre:

- scenario family;
- target mind;
- language;
- route tag;
- decision class;
- review status;
- source claim;
- base model;
- adapter;
- split.

Dodaj side-by-side review treh razumov. Reviewer mora videti vse tri, da lahko zazna konvergenco, vendar potrjuje vsakega posebej.

## 14.4 Canon panel

Omogoči:

- pregled claimov;
- slovensko besedilo;
- angleški gloss;
- vir in stran;
- status;
- open question;
- implementation hypothesis;
- opozorilo, če prompt vsebuje deprecated claim.

---

# 15. Konkretni posegi po obstoječih datotekah

## `app/backend/rei/profiles.py`

- dodaj ordinalni parser;
- `PROFILE_WEIGHTS` označi legacy;
- nova funkcija `profile_authority(profile) -> CharacterAuthority`;
- nobena nova odločitev ne uporablja float uteži.

## `app/backend/rei/engine.py`

- ohrani stari `run_rei_cycle` za baseline;
- dodaj `run_rei_cycle_v2`;
- procesorje poženi enkrat in brez profila;
- odstrani `_situational_driver` iz v2 odločanja;
- odstrani `_resultant_pressure` iz v2;
- ne kliči `_llm_ego_resultant` v v2;
- pokliči `arbitrate`;
- nato opcijsko `render_racio_narration`.

## `app/backend/rei/acceptance.py`

- označi kot legacy;
- nova `acceptance_v2.py` naj ne sklepa sprejemanja iz besede “bounded”;
- v controlled evalih je acceptance eksplicitni input;
- poznejši classifier naj ima ločen dataset.

## `knowledge/canon/processor_contracts.json`

- ne popravljaj več z novimi scenarijskimi pravili;
- zamrzni kot v1;
- izdelaš v2 brez business-specific navodil.

## `app/backend/rei/contract_loader.py`

- podpira `canon_version`;
- default v legacy ostane v1;
- v2 uporablja claims in glossary;
- jezikovni builder sestavi mixed SL/EN prompt.

## `app/backend/rei/ft_dataset.py`

- nova schema version;
- večjezični manifest;
- scenario family split;
- ločeni review statusi;
- source claim IDs;
- semantic validation;
- adapter target;
- prepreči train export review-only in neodobrenih primerov.

## `scripts/generate_rei_ft_dataset.py`

- preimenuj v legacy ali ohrani;
- nova skripta `build_rei_dataset_v2.py`;
- ne kliče teacher modela za “gold” brez review workflowa;
- procesor bundle generira enkrat;
- profile outputs so deterministic fixtures;
- situational override se odstrani.

## `app/gui/`

- profile selector odstrani iz processor runa;
- doda arbitration tab;
- doda bilingual/canon review;
- doda base-vs-adapter eval.

## `CURRENT.md` in `README.md`

- trenutni opis je zastarel glede aktivnega GUI-ja in dataset workbencha;
- jasno loči:
  - legacy baseline;
  - canonical-v2 experimental engine;
  - active developer tooling;
  - training pipeline.

---

# 16. Testni paket

Dodaj najmanj:

```text
tests/v2/test_canon_claim_registry.py
tests/v2/test_no_scenario_rules_in_canon.py
tests/v2/test_profile_authority_parser.py
tests/v2/test_single_leader_arbitration.py
tests/v2/test_ordered_profile_arbitration.py
tests/v2/test_pair_profile_conflict.py
tests/v2/test_thirteenth_majority.py
tests/v2/test_spoznanje_detection.py
tests/v2/test_task_delegation.py
tests/v2/test_operational_controller.py
tests/v2/test_situation_never_changes_structural_rank.py
tests/v2/test_processor_profile_blindness.py
tests/v2/test_mind_input_routing.py
tests/v2/test_same_behavior_different_route.py
tests/v2/test_keyword_traps.py
tests/v2/test_acceptance_not_equal_behavior.py
tests/v2/test_narrator_cannot_change_decision.py
tests/v2/test_bilingual_semantic_alignment.py
tests/v2/test_dataset_family_split.py
tests/v2/test_training_export_requires_approval.py
tests/v2/test_adapter_metadata_base_match.py
```

## Property-based testi

Kjer je smiselno, uporabi Hypothesis:

- permutacije profilov;
- naključne confidence vrednosti ne smejo spremeniti ordinalnega vodje;
- pri REI mora vsaka 2-of-3 večina vrniti isto možnost;
- noben lower-tier intensity ne prepiše top-tier authority;
- narrator ne more spremeniti `selected_option_id`.

---

# 17. Faze in commiti

## Faza 0 - zamrznitev stanja

**Namen:** reproducibilna izhodiščna točka.

Naloge:

- preveri `git status`;
- ustvari tag ali zapis baseline SHA;
- shrani seznam testov in trenutne rezultate;
- zapiši aktivne modele in runtime;
- popravi `CURRENT.md`, da GUI ni pomotoma opisan kot arhiviran;
- ne spreminjaj behaviorja.

Predlagan commit:

```text
docs: freeze legacy REI baseline and document active tooling
```

Izhodni pogoj:

- stari testi nespremenjeno uspejo;
- baseline run se še vedno zažene;
- dokumentacija loči legacy in v2.

## Faza 1 - kanon v2

Naloge:

- claim registry;
- glossary;
- source page map;
- open questions;
- označitev weighted synthesis note kot hipoteze;
- odstranitev scenarijskih pravil iz novega kanona;
- validator.

Commit:

```text
feat(canon): add source-traceable bilingual REI canon v2
```

Izhodni pogoj:

- vsak core claim ima vir;
- noben core processor claim ne omenja konkretnega benchmark scenarija;
- slovenski kanon je source of truth.

## Faza 2 - modeli in ordinalni profili

Naloge:

- `models_v2.py`;
- `profile_authority`;
- compatibility mapping;
- truth tables.

Commit:

```text
feat(core): add ordinal character authority and v2 schemas
```

Izhodni pogoj:

- vseh 13 profilov ima pravilne tiers;
- nobena v2 funkcija ne potrebuje float uteži.

## Faza 3 - deterministični arbitrator

Naloge:

- `arbitration.py`;
- single/ordered/pair/REI rules;
- spoznanje;
- delegation;
- operational controller;
- tests.

Commit:

```text
feat(core): implement canonical ordinal arbitration
```

Izhodni pogoj:

- 100 % truth-table testov;
- 0 situacijskih sprememb značaja;
- pair conflict ostane eksplicitno nerešen.

## Faza 4 - profilno slepi procesorji

Naloge:

- nov v2 processor runner;
- odstranitev profila iz payloadov;
- frozen bundle;
- profile matrix reuse;
- diagnostics.

Commit:

```text
feat(processors): isolate profile-blind REI mind proposals
```

Izhodni pogoj:

- isti bundle se uporabi za 13 profilov;
- processor payload ne vsebuje profila;
- matrični LLM klici se občutno zmanjšajo.

## Faza 5 - SceneFrame in routing

Naloge:

- neutral parser;
- evidence IDs;
- mind packets;
- bilingual input;
- no direct-authority keywords.

Commit:

```text
feat(perception): add neutral scene frame and mind-specific routing
```

Izhodni pogoj:

- vsak signal je sledljiv do evidence ID;
- E/I direct-access caveat je vedno prisoten;
- route tests uspejo.

## Faza 6 - acceptance v2 in narrator

Naloge:

- eksplicitni acceptance state;
- legacy heuristic deprecated;
- Racio narrator;
- immutable resultant;
- conscious decision vs predicted behavior.

Commit:

```text
feat(resultant): separate acceptance, behavior and Racio narration
```

Izhodni pogoj:

- narrator ne more spremeniti core rezultata;
- bounded action ni avtomatsko accepting;
- spoznanje in acceptance sta ločena.

## Faza 7 - eval v2

Naloge:

- gold-mini;
- contrast fixtures;
- bilingual eval;
- adversarial eval;
- HTML/Markdown report.

Commit:

```text
feat(eval): add causal profile and processor-route evaluation
```

Izhodni pogoj:

- base modeli dobijo reproducibilno baseline oceno;
- action collapse je viden;
- keyword trap failures so izmerjeni.

## Faza 8 - dataset workbench v2

Naloge:

- family editor;
- review statuses;
- source claims;
- bilingual alignment;
- exports per target adapter.

Commit:

```text
feat(dataset): add reviewed bilingual processor dataset workflow
```

Izhodni pogoj:

- gold-mini je mogoče v celoti pregledati v GUI;
- neodobren primer ne more v train export;
- split leakage test uspe.

## Faza 9 - QLoRA pipeline

Naloge:

- training folder;
- HF base registry;
- three adapters;
- training/eval scripts;
- metadata;
- smoke run.

Commit:

```text
feat(training): add reproducible per-processor QLoRA pipeline
```

Izhodni pogoj:

- 1 majhen base model se lahko trenira end-to-end;
- adapter se naloži v PEFT provider;
- base vs adapter report je ustvarjen.

## Faza 10 - realni adapterji in deployment

Naloge:

- tri adapter train rune;
- izbor checkpointov;
- Ollama direct/merge export;
- parity tests;
- GUI model selection.

Commit:

```text
feat(runtime): integrate validated REI adapters and deployment export
```

Izhodni pogoj:

- vsi adapterji presegajo base po dogovorjenih metrikah;
- export ne spremeni odločilne semantike;
- end-to-end v2 simulacija deluje v slovenščini.

---

# 18. Kaj Codex izrecno ne sme narediti

1. Ne spreminjaj karakterne hierarhije na podlagi keywordov.
2. Ne dodajaj nove decimalne situacijske bonuse.
3. Ne pošiljaj profila posameznim procesorjem v controlled mode.
4. Ne pusti LLM-ju, da sam določi decision authority.
5. Ne treniraj “Ego adapterja” pred determinističnim arbitratorjem.
6. Ne obravnavaj validnega JSON-a kot kakovostnega gold primera.
7. Ne treniraj na `review_only` matrix outputih.
8. Ne uporabljaj naključnega splitanja posameznih vrstic; split je po family.
9. Ne dodajaj konkretnega scenarija v kanonični processor prompt.
10. Ne uporabljaj action keywords kot glavno ground truth.
11. Ne prevajaj slovenskih REI terminov brez glossary ID-ja.
12. Ne treniraj dolgih chain-of-thought zapisov.
13. Ne mešaj metafizičnih in medicinskih trditev iz PDF-ja v core simulator.
14. Ne razglašaj simulacije za diagnozo ali dokaz karakterja resnične osebe.
15. Ne predpostavljaj, da Ollama neposredno podpira adapter izbrane arhitekture.
16. Ne mergeaj oziroma kvantiziraj adapterja, preden ni uspešno ocenjen v PEFT referenci.
17. Ne znižuj quality gate samo zato, da run izgleda uspešen.
18. Ne briši legacy poti, dokler v2 nima parity in migration dokumentacije.

---

# 19. Ločitev varnega jedra od spornih vsebin

Dokument *Eros - pogovori.pdf* vsebuje poleg procesorskega modela tudi:

- medicinske trditve;
- trditve o boleznih;
- metafizične trditve o Življenju in kontinuumih;
- zgodovinske interpretacije;
- trditve o spolu, genetiki in družbenih skupinah;
- potencialno manipulativno občutljivo znanje.

V `claims_v2` dodaj `risk_class`:

```text
core
medical_claim
metaphysical_claim
social_generalization
historical_claim
manipulation_sensitive
exclude_from_training
```

QLoRA processor dataset naj privzeto uporablja samo:

- `core`;
- `character_arbitration`;
- `perception`;
- `processing_route`;
- `cooperation_and_acceptance`;
- `language_and_translation`.

Sporne trditve lahko ostanejo v raziskovalnem arhivu, ne smejo pa postati samodejni odgovor simulatorja.

---

# 20. Definition of done

Projekt je bližje cilju šele, ko velja vse naslednje:

- Racio, Emocio in Instinkt na isti situaciji ustvarijo ločene, kanonično prepoznavne poti;
- njihov predlog ni odvisen od profila, ki bo uporabljen kasneje;
- ista trojica predlogov se lahko požene skozi vseh 13 značajev;
- hierarhija je ordinalna in stabilna;
- situacija spremeni signal, ne značaja;
- delegacija je ločena od avtoritete;
- trinajsti uporablja 2-of-3;
- parni konflikt se ne zakrije z umetnim povprečjem;
- zavestna odločitev je ločena od predvidenega vedenja;
- spoznanje je ločena all-three convergence oznaka;
- končni tekst je Racijev prevod, ne četrti agent;
- slovenski kanon ostane semantični vir;
- angleščina je sledljiv gloss;
- dataset je človeško pregledan;
- QLoRA izboljša procesorje, ne prepisuje pravil odločanja;
- export v Ollama ohrani rezultat PEFT reference;
- evali merijo notranjo pot, ne samo besede.

---

# 21. Prvi neposredni prompt za Codex

Spodnje navodilo uporabi kot prvo izvedbeno nalogo. Ne naroči mu še celotnega refactorja.

```text
Preglej dokument REI_v3_Codex_canonical_v2_QLoRA_plan_2026-07-10.md in izvedi samo Fazo 0 in Fazo 1.

Cilji:
1. Zamrzni in dokumentiraj trenutni legacy baseline brez spremembe runtime vedenja.
2. Posodobi CURRENT.md in README.md tako, da jasno ločita:
   - legacy 156-case baseline,
   - aktivni GUI/dataset workbench,
   - načrtovani canonical-v2 engine.
3. Dodaj source-traceable bilingual canon v2:
   - knowledge/canon/claims_v2.jsonl
   - knowledge/canon/processors_v2.yaml
   - knowledge/canon/character_rules_v2.yaml
   - knowledge/canon/open_questions_v2.md
   - knowledge/glossary/rei_terms_v2.yaml
4. Vnesi začetne core claime iz načrta s slovenskimi izvirnimi formulacijami, angleškimi glosi, vrsto vira in stranjo.
5. Dokument REI_weighted_synthesis_working_note.md označi kot implementation hypothesis, ki je po novem neposrednem pregledu virov delno superseded. Ne briši ga.
6. V novi kanon ne kopiraj nobenih benchmark-specific pravil o quit-job, runway, side-hustle ali first business scenario.
7. Dodaj validator in teste:
   - vsak core claim ima source_file in page ali jasen OD dokument;
   - vsak claim ima status in risk_class;
   - novi processor canon ne vsebuje scenario-specific fraz;
   - slovenski canonical text je obvezen;
   - angleški gloss je ločen od canonical texta.
8. Ne spreminjaj engine.py, profiles.py, acceptance.py ali trenutnih promptov v tej fazi.
9. Zaženi vse teste in poročaj:
   - git diff povzetek,
   - ustvarjene datoteke,
   - rezultate testov,
   - odprta vprašanja,
   - predlagan commit message.

Ustavi se po Fazi 1 in počakaj na pregled.
```

---

# 22. Prednostni vrstni red

Če je časa malo, je vrstni red brez kompromisa:

1. ordinalni kanon in pravilna odločitev;
2. profilno slepi procesorji;
3. deterministic arbitration;
4. gold-mini dataset;
5. eval v2;
6. šele nato QLoRA;
7. šele nato večji modeli in Ollama deployment.

Največja nevarnost projekta je, da bi dober QLoRA zelo učinkovito utrdil napačno razumevanje REI. Največja priložnost pa je ravno nasprotna: ker so pravila hierarhije dovolj strukturirana, lahko LLM omejimo na tisto, v čemer je dober - jezik, prizore, semantično presojo in prevajanje - ter mu ne prepustimo odločevalne matematike, ki jo lahko zanesljivo in pregledno izvaja koda.
