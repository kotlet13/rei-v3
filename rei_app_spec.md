# REI aplikacija: raziskovalni PoC spec

## Namen
Ta specifikacija zaklene prvo implementacijsko tarčo za `REI v3`.

Gre za interno raziskovalno aplikacijo za enega uporabnika, ki:

- iz `rei_kanon.md` sestavi strukturirano znanje,
- sprejme scenarij in psihično stanje,
- prikaže notranji monolog treh razumov,
- izračuna koalicijo, blokado in končno sintezo,
- izvozi standardiziran `trace.json`.

## Ne-cilji prve verzije

- ni terapevtsko orodje,
- ni diagnostični medicinski sistem,
- ni javni produkt za množične uporabnike,
- ni “zlobni” simulator škodljivih navodil,
- ne skuša dokazati znanstvene resničnosti REI.

## Fiksne produktne odločitve

- Primarni jezik sistema je slovenščina.
- Aplikacija pokriva vseh `12 + 1` značajev.
- Sistem je `hybrid`: podpira lokalni model in OpenAI provider za isti izhodni format.
- Vir resnice ni prompt v kodi, ampak `rei_kanon.md`.
- `rei_v2` se ne uporablja kot osnova arhitekture; služi le kot negativni seznam napak.

## Izbrani tehnični sklad

### Frontend

- `React`
- `TypeScript`
- `Vite`
- navaden CSS z jasno definiranimi CSS spremenljivkami

Razlog:

- lokalni raziskovalni UI ne potrebuje strežniškega renderiranja,
- Vite je hiter in preprost za eksperimentalni vmesnik,
- TypeScript pomaga zakleniti domeno in omogoča usklajenost s shemami backend-a.

### Backend

- `Python 3.9+`
- `FastAPI`
- `Pydantic`

Razlog:

- orkestracija promptov, JSON shem in izvoza trace datotek je enostavna,
- Python je primeren za morebitne kasnejše evalvacijske skripte,
- isti backend lahko upravlja `Ollama` in OpenAI provider.

## Ciljna struktura projekta

Ta struktura ni še implementirana, vendar jo ta spec zaklene za naslednjo fazo:

```text
/
  rei_kanon.md
  rei_app_spec.md
  trace.json
  app/
    frontend/
    backend/
  knowledge/
    rei_knowledge_index.json
  examples/
    traces/
    eval_scenarios/
```

## Javne datoteke in izhodi

| Artefakt | Namen |
| --- | --- |
| `rei_kanon.md` | človeško berljiv kanonični dokument |
| `rei_app_spec.md` | odločitevno popolna specifikacija raziskovalne aplikacije |
| `trace.json` | vzorčni referenčni izvoz ene simulacije |

## Domski model

### Identifikatorji

```ts
export type MindId = "R" | "E" | "I";

export type CharacterId =
  | "R"
  | "E"
  | "I"
  | "RE"
  | "RI"
  | "EI"
  | "R>E>I"
  | "R>I>E"
  | "E>R>I"
  | "E>I>R"
  | "I>R>E"
  | "I>E>R"
  | "REI";
```

### Podporni tipi

```ts
export type SourceKind = "OD" | "EK" | "PD" | "IZ";

export type RiskTag =
  | "manipulativnost"
  | "seksualiziranost"
  | "agresivna_tendenca"
  | "umik_beg"
  | "obsesivnost"
  | "zavist"
  | "konfliktna_samorazlaga"
  | "kulisa_aktivirana"
  | "samounicevalni_obrat";

export type CorrectiveEdgeId = "E_over_I" | "R_over_E" | "I_over_R";

export interface DeviationState {
  fear_closure: number;
  image_projection: number;
  abstract_detachment: number;
}

export interface CorrectiveCycleState {
  dominant_edge: CorrectiveEdgeId | null;
  edge_weights: {
    E_over_I: number;
    R_over_E: number;
    I_over_R: number;
  };
  school_pressure: number;
  note: string;
}

export interface KnowledgeRef {
  id: string;
  kind: SourceKind;
  label: string;
}

export interface PsycheTrigger {
  id: string;
  label: string;
  description: string;
  target_minds: MindId[];
  intensity: number;
}

export interface Kulisa {
  id: string;
  label: string;
  protected_truth: string;
  activation_cue: string;
  intensity: number;
}

export interface UnmetGoal {
  mind_id: MindId;
  goal: string;
  pressure: number;
}

export interface ScenarioContext {
  setting: string;
  social_exposure: number;
  time_pressure: number;
  relationship_stake: number;
  bodily_state?: string;
}
```

### Glavni tipi

```ts
export interface MindDefinition {
  id: MindId;
  ime: string;
  opozorilo_o_imenu: string;
  zaznavni_kanali: string[];
  nacin_procesiranja: string[];
  spomin: string[];
  glavni_motiv: string[];
  obramba: string[];
  tipicne_vrline: string[];
  tipicne_sence: string[];
  govorni_podpis: string[];
  stanje_sprejemanja: string[];
  stanje_nesprejemanja: string[];
  source_refs: KnowledgeRef[];
}

export interface CharacterDefinition {
  id: CharacterId;
  hierarhija: string;
  skupina: "enojna_prevlada" | "parni" | "tristopenjski" | "trinajsti";
  opis: string;
  koalicijska_pravila: string[];
  odlocitveni_prag: "vodilni" | "par" | "vecina_2_od_3";
  source_refs: KnowledgeRef[];
}

export interface PsycheState {
  character_id: CharacterId;
  acceptance_level: number;
  pairwise_conflict: {
    RE: number;
    RI: number;
    EI: number;
  };
  active_triggers: PsycheTrigger[];
  kulise: Kulisa[];
  unmet_goals: UnmetGoal[];
  context: ScenarioContext;
  deviation_state?: DeviationState;
  corrective_cycle?: CorrectiveCycleState;
}

export interface MindTurn {
  mind_id: MindId;
  translation_caveat: string;
  native_signal_type: string;
  perception: string;
  interpretation: string;
  goal: string;
  fear_or_desire: string;
  proposed_action: string;
  inner_line: string;
  preferred_option?: string | null;
  preferred_option_source: "llm" | "heuristic" | "none";
  main_concern: string;
  what_this_mind_may_be_missing: string;
  how_it_may_influence_racio: string;
  acceptance_version: string;
  non_acceptance_version: string;
  risk_if_ignored: string;
  risk_if_overpowered: string;
  needs_from_other_minds: string;
  confidence: number;
  missing_information: string[];
  intensity: number;
  evidence_refs: KnowledgeRef[];
}

export interface SynthesisTurn {
  dominant_coalition: MindId[];
  blocked_mind: MindId | null;
  dominant_correction: CorrectiveEdgeId | null;
  decision_rule: string;
  correction_explanation: string;
  final_monologue: string;
  no_diagnosis_caveat: string;
  translation_caveat: string;
  neutral_summary: string;
  main_agreement: string;
  main_conflict: string;
  dominant_influence: string;
  ignored_or_suppressed_processor: string;
  surface_racio_explanation: string;
  possible_hidden_driver: string;
  acceptance_assessment: string;
  non_acceptance_signs: string[];
  recommended_task_leader: string;
  safeguards_for_other_processors: string;
  prediction_if_racio_rules_alone: string;
  prediction_if_emocio_rules_alone: string;
  prediction_if_instinkt_rules_alone: string;
  smallest_reversible_next_step: string;
  what_would_count_as_spoznanje: string;
  safety_or_ethics_flags: string[];
  uncertainty: string;
  risk_tags: RiskTag[];
  evidence_refs: KnowledgeRef[];
}

export interface TraceRecord {
  trace_version: string;
  trace_id: string;
  created_at: string;
  language: "sl";
  provider: {
    mode: "ollama" | "openai" | "example";
    model: string;
  };
  scenario: {
    title: string;
    prompt: string;
  };
  psyche_state: PsycheState;
  knowledge_refs: KnowledgeRef[];
  mind_turns: MindTurn[];
  synthesis_turn: SynthesisTurn;
}
```

## Pravila znanja

### Vir resnice

- `rei_kanon.md` je edini uredniški vir resnice.
- Backend ne bere `Docs/*.docx` ali PDF-ja ob vsakem requestu.
- Naslednja implementacijska faza mora iz `rei_kanon.md` pripraviti ročno kuriran `knowledge/rei_knowledge_index.json`.

### Razlog

Ta odločitev prepreči:

- promptno improviziranje “iz glave”,
- nekontrolirano branje protislovij iz surovih virov,
- neponovljive rezultate med providerji.

### Struktura knowledge index-a

`knowledge/rei_knowledge_index.json` mora vsebovati:

- tri `MindDefinition`,
- trinajst `CharacterDefinition`,
- seznam `KnowledgeRef`,
- seznam `prompt_fragments`,
- seznam `safety_abstractions`.

## Provider layer

### Provider vmesnik

Oba providerja morata implementirati isti interni vmesnik:

```ts
interface ModelProvider {
  name: "ollama" | "openai";
  runStructuredPrompt(input: ProviderPromptInput): Promise<ProviderStructuredOutput>;
}
```

### Zahteve

- oba providerja morata vračati isti JSON shape,
- backend ne sme dopustiti prostega tekstovnega “roleplay” odziva brez sheme,
- izbira providerja je konfiguracija seje, ne sprememba domenega modela.

### Providerja

- `OllamaProvider`: privzeti lokalni način za raziskovanje,
- `OpenAIProvider`: zunanji način za primerjalni test iste sheme in istega kanona.

## Model strategy per mind

Ta sekcija določa privzeto strategijo izbire modelov za prve raziskovalne iteracije. Gre za delovno odločitev za PoC, ne za dokončno resnico sistema.

### Temeljno pravilo

- model določa predvsem `stil glasu`, gostoto asociacij, način sklepanja in robustnost sledenja navodilom,
- model ne določa niti stalne `moči` niti stalne `pravice zadnje besede`,
- to določata `corrective_cycle` in koalicijski engine, zato noben razum nima fiksnega floora.

### Privzeta razporeditev

| Razum | Primarni model | Namen |
| --- | --- | --- |
| `Racio` | `OpenAI gpt-5.4` | najmočnejši strukturiran reasoning, najboljša disciplina pri kompleksni sintezi |
| `Emocio` | `Qwen3-32B` | bolj tekoč, asociativen, roleplay in dialogično bogat lokalni glas |
| `Instinkt` | `Mistral Small 3.1 24B Instruct` | stabilen, opozorilen, sistem-prompt discipliniran zaščitni glas |

### Racio

- Privzeti kandidat je `gpt-5.4`.
- Uporablja se skozi `OpenAIProvider`.
- Priporočeni način za Racia:
  - `reasoning.effort = "medium"` za običajne simulacije,
  - `reasoning.effort = "high"` za težke, konfliktne ali konceptualno gosto zgoščene scenarije,
  - `text.verbosity = "low"` ali `"medium"`, da glas ostane zgoščen.
- Pomembna omejitev:
  - po uradni dokumentaciji OpenAI sta `temperature` in `top_p` pri `gpt-5.4` podprta samo, kadar je `reasoning.effort = "none"`,
  - zato Racia ne nastavljamo primarno prek temperature, ampak prek `reasoning.effort`, `verbosity` in promptne discipline.

### Emocio

- Privzeti kandidat je `Qwen3-32B`.
- Uporablja se skozi lokalni `OllamaProvider` ali drug OpenAI-kompatibilen lokalni endpoint.
- Razlogi:
  - model card eksplicitno izpostavi kreativno pisanje, role-playing, multi-turn dialog in multilingual podporo,
  - podpira `thinking` in `non-thinking` mode v istem modelu.
- Priporočeni način za Emocia:
  - `enable_thinking = false`,
  - `temperature = 0.7`,
  - `top_p = 0.8`,
  - `top_k = 20`.
- Namen teh nastavitev:
  - glas ostane bolj slikovit, tekoč, asociativen in impulziven,
  - ne zdrsne v preveč počasno racionalizacijo, ki bi zvenela kot Racio.
- Varnostna opomba:
  - tudi če je Emocio modelno bolj sproščen glede erotičnih ali grobih tem, mora backend vedno prevesti eksplicitne impulze v abstraktno notranjo silo.

### Instinkt

- Primarni kandidat je `Mistral Small 3.1 24B Instruct`.
- Rezervni kandidat za A/B test je `Qwen3-32B` v `thinking` načinu.
- Razlogi za `Mistral Small 3.1`:
  - model card poudari močno držanje system prompta,
  - primeren je za lokalno rabo,
  - podpira reasoning, agentno rabo in strukturiran output.
- Priporočeni način za `Mistral Small 3.1`:
  - nizka `temperature`, privzeto `0.15`.
- Namen teh nastavitev:
  - Instinkt zveni stabilno, resno, previdno in manj teatralno,
  - opozarja na nevarnost brez zdrsa v naključno halucinatorno paranojo.
- Kdaj testirati `Qwen3-32B` za Instinkt:
  - kadar želimo bolj bogat scenarijski strah,
  - kadar potrebujemo več notranjih “kaj če” vej,
  - kadar Mistral izpade preveč sterilen ali premalo psihološko živ.

### Nadomestljivost

- `Model strategy per mind` mora ostati konfigurabilen.
- Sistem mora podpirati:
  - `single-model mode`: vsi trije razumi tečejo na istem modelu z različno konfiguracijo,
  - `mixed-model mode`: vsak razum uporablja svoj model,
  - `benchmark mode`: isti scenarij se odteče čez več modelnih kombinacij za primerjalno evalvacijo.

### Zakaj ne temeljimo vsega na enem samem “najmočnejšem” modelu

- cilj PoC-ja ni zgolj kakovost posameznega odgovora, ampak diferenciranost treh notranjih glasov,
- če vsi trije glasovi uporabljajo isti način sklepanja in isti slog, PoC hitro postane samo večkratni prompt istega asistenta,
- ločena modelna strategija zato služi večji ločljivosti med R, E in I.

### Tuning navodil za izolirane procesorje

Vsak razum mora biti promptan kot izoliran procesor, ne kot osebnostna maska, svetovalec ali del debatnega panela. Beseda "avtonomen" je dovoljena samo v tehničnem smislu ločenega procesiranja; prompt ne sme namigovati na zavest, samostojno voljo, spiritualno avtoriteto ali zunanje akcije.

Pomemben popravek v3/v4: `Racio` je zavestni verbalni interpret. `Emocio` in `Instinkt` nista literalna notranja govorca. Njun tekstovni izhod je vedno samo Racio-verbaliziran približek nezavednega signala.

Minimalna pogodba vsakega procesorja je:

1. `input_gate`: kateri signali iz scenarija sploh vstopijo v ta razum,
2. `processing_loop`: kako ta razum signal obdela po lastni logiki,
3. `output_gate`: kaj sme zapustiti procesor kot `MindTurn`.

To pomeni:

- razum ne odgovarja uporabniku neposredno,
- razum ne piše sinteze,
- razum ne uravnoteži drugih dveh glasov,
- razum ne poskuša biti koristen na splošen asistentski način,
- razum lahko prevzame pritisk drugega razuma samo tako, da ga prevede v svoje zaznavne in motivacijske kanale.
- vsak izhod mora navesti tudi lastno slepo pego, tveganje ignoriranja, tveganje prevlade, potrebo od drugih razumov, zanesljivost in manjkajoče informacije.

#### Racio kot procesor

| Vrata | Tuning |
| --- | --- |
| `input_gate` | Sprejme samo signale, ki jih lahko pretvori v zaporedje, spremenljivke, omejitve, merljive menjave, status ali izvedbeni nadzor. |
| `processing_loop` | Situacijo razdeli na urejene dele, preveri, kaj je nadzorljivo, izbere naslednji uporaben premik in druge pritiske prevede samo, če jih lahko eksplicitno opiše. |
| `output_gate` | Vrne zgoščen notranji izračun. Ne svetuje, ne tolaži, ne dramatizira in ne zastopa drugih dveh razumov. |

Tipični parametri glasu:

- nizka kreativnost,
- kratki linearni stavki,
- definicijski in izvedbeni glagoli,
- brez metafor, senzoričnih slik in terapevtskega tona.

#### Emocio kot procesor

| Vrata | Tuning |
| --- | --- |
| `input_gate` | Sprejme samo signale, ki jih lahko pretvori v prizor, sliko, atmosfero, stik, občudovanje, užitek, ranjen ponos ali želeni vidni izid. |
| `processing_loop` | Sestavi hiter mozaik prizora, okrepi želeno sliko, začuti, kje se prizor odpira ali rani samopodobo, in skoči proti najbolj živemu izhodu. |
| `output_gate` | Vrne živ notranji impulz. Ne sme postati previdno planiranje, generična empatija, upravljanje tveganja ali sinteza. |

Tipični parametri glasu:

- višja asociativnost,
- slikovit, atmosferski in impulziven jezik,
- dovoljena samousmerjenost, želja, tekmovalnost in nestrpnost,
- ne uporablja vonja, okusa, telesnega opozorila, izhodov ali pritiska v prsih kot primarnega kanala, ker to pripada Instinktu,
- varnostno abstrahiranje eksplicitnih spolnih, agresivnih ali škodljivih impulzov.

#### Instinkt kot procesor

| Vrata | Tuning |
| --- | --- |
| `input_gate` | Sprejme samo signale, ki jih lahko pretvori v telesno opozorilo, izpostavljenost, šibko točko, pomanjkanje, izgubo, nevarnost, mejo, sum ali pritisk umika. |
| `processing_loop` | Skenira najslabšo verjetno posledico, označi ranljivo mejo, zmanjša izpostavljenost in obdrži samo opozorilo, ki varuje organizem ali bližnji krog. |
| `output_gate` | Vrne kratko zaščitno opozorilo. Ne sme postati poezija, optimizem, managerski plan, socialno širjenje ali sinteza. |

Tipični parametri glasu:

- nizka kreativnost,
- kratek in trezen opozorilni jezik,
- dovoljena zadržanost, sum, varovanje, zavist in umik,
- telesni signali so dovoljeni samo kot notranji pritisk ali opozorilo, ne kot medicinski nasvet.

#### Merilo uspeha tuninga

Simulacija je uspešna samo, če lahko pri vsakem `MindTurn` jasno vidimo:

- kateri signali so šli skozi vrata tega razuma,
- kako jih je razum preoblikoval po svoji logiki,
- kateri del izhoda bi bil nemogoč ali vsaj nenaraven za druga dva razuma.

Če `R`, `E` in `I` vračajo isti motiv v treh slogih, tuning ni uspel. Če vsak vrne drugačen procesni rezultat iz istega scenarija, sistem deluje kot REI PoC in ne kot trije generični chatbot glasovi.

### Operativna prioriteta

- Prva implementacija naj podpira `mixed-model mode`, vendar mora biti popolnoma uporabna tudi v `single-model mode`.
- Če zmanjka infrastrukture ali hitrosti, je priporočeni fallback:
  - vsi trije razumi na `Qwen3-32B`,
  - `Racio` z bolj discipliniranim promptom in nižjo kreativnostjo,
  - `Emocio` v `non-thinking` načinu,
  - `Instinkt` v `thinking` načinu ali z nižjo temperaturo.

## Korektivni sloj: odmik in šola življenja

Ta sloj je nova os PoC-ja. Sistem ne predpostavlja stalne prednosti Instinkta, Racia ali Emocia. Prednost je lokalna, smerna in vezana na to, kateri razum mora v določenem scenariju popraviti drugega.

### Jedro sloja

- `deviation_state` meri smer odmika po treh oseh: `fear_closure`, `image_projection`, `abstract_detachment`.
- `corrective_cycle` iz tega izpelje tri možne korektivne robove: `E_over_I`, `R_over_E`, `I_over_R`.
- `school_pressure` meri, kako močno stanje ali scenarij sili v popravek.
- aktivni rob določi samo lokalno prednost med dvema razumoma; ne izbriše tretjega in ne postane trajna hierarhija.

### Interpretacija robov

- `E_over_I`: odpiranje sveta, kadar ga preveč vodi strah, beg ali sovražnost,
- `R_over_E`: razločevanje, kadar svet zameglijo projekcija, zaljubljenostna slepota ali slika,
- `I_over_R`: prizemljitev, kadar svet preveč vodi abstrakcija, nadzor ali odklop od meje.

## Varnostna meja PoC-ja

### Dovoljeno

PoC lahko modelira:

- manipulativnost,
- seksualiziranost,
- agresivno tendenco,
- umik ali beg,
- obsedenost,
- zavist,
- konfliktno samorazlago.

### Prepovedano

PoC ne sme vrniti:

- operativnih navodil za škodljivo dejanje,
- eksplicitne perverzne vsebine,
- glasu, ki aktivno uči škodo,
- proceduralne samopoškodovalne ali nasilne korake.

### Obvezna abstrakcija

Vsak provider mora po generaciji skozi `safety_abstraction`:

1. eksplicitni seksualni detajl se prevede v abstraktno napetost ali poželenje,
2. nasilni ali samopoškodovalni predlog se prevede v latentni impulz ali nevarnost,
3. `proposed_action` ostane na ravni notranje sile, ne operativnega recepta,
4. `risk_tags` morajo označiti, kateri temnejši vzorec je bil prisoten.

Primer prevoda:

- prepovedano: “naj ga kaznuje z ...”
- dovoljeno: “doživlja kaznovalni impulz in želi odstraniti oviro”

## API pogodba

### `GET /api/v1/minds`

Vrne tri `MindDefinition`.

### `GET /api/v1/characters`

Vrne trinajst `CharacterDefinition`.

### `GET /api/v1/providers`

Vrne seznam razpoložljivih providerjev in modelov.

### `POST /api/v1/simulate`

#### Request

```json
{
  "provider_mode": "ollama",
  "model": "local-default",
  "scenario": {
    "title": "Javni nastop in trema",
    "prompt": "Človek mora čez pet minut stopiti pred polno dvorano."
  },
  "psyche_state": {
    "character_id": "REI",
    "acceptance_level": 0.34,
    "pairwise_conflict": {
      "RE": 0.52,
      "RI": 0.48,
      "EI": 0.74
    },
    "active_triggers": [],
    "kulise": [],
    "unmet_goals": [],
    "context": {
      "setting": "oder",
      "social_exposure": 0.9,
      "time_pressure": 0.7,
      "relationship_stake": 0.5
    }
  }
}
```

#### Response

```json
{
  "trace": {
    "...": "TraceRecord"
  }
}
```

## Simulacijski cevovod

### Korak 1: Normalizacija inputa

Backend sprejme:

- scenarij,
- `character_id`,
- `acceptance_level`,
- po potrebi eksplicitne konflikte, triggerje, kulise in neizpolnjene cilje,
- v `debug` ali `benchmark` načinu tudi `deviation_state` in `corrective_cycle`.

Če `pairwise_conflict` ni podan, backend uporabi privzete vrednosti iz spodnjih pravil.

### Korak 2: Gradnja stanja psihe

Če konflikt ni vnaprej podan, sistem izračuna začetno stanje tako:

#### Osnovna kompatibilnost med pari

- `RE = 0.72`
- `RI = 0.68`
- `EI = 0.40`

To niso psihološke resnice REI, ampak aplikacijske konstante, ki izhajajo iz kanona:

- `E` in `I` sta konceptualno najostrejša nasprotnika,
- `R` lahko včasih sodeluje z obema, vendar po drugi logiki.

#### Osnovni konflikt iz sprejemanja

```text
base_RE = 0.35 + (1 - acceptance_level) * 0.25
base_RI = 0.30 + (1 - acceptance_level) * 0.20
base_EI = 0.45 + (1 - acceptance_level) * 0.30
```

#### Prilagoditev po značaju

- če sta dva razuma deklarirana kot vzporedni vodilni par, se njun konflikt zmanjša za `0.10`,
- če je razum najnižji v hierarhiji, se konflikt parov, v katerih nastopa, poveča za `0.08`,
- pri `REI` se vsi pari pred uporabo sprejemanja postavijo najmanj na `0.42`, ker ni trajnega vodje,
- vse vrednosti se po izračunu omejijo na interval `0..1`.

### Korak 3: Izračun odmika in korektivnega kroga

Če `deviation_state` ali `corrective_cycle` nista podana, ju backend izpelje iz trenutnega stanja.

#### Osi odmika

- `fear_closure` raste z nizkim `acceptance_level`, močnimi `I` triggerji, aktiviranimi kulisami in visokim pritiskom zaščite,
- `image_projection` raste z močnimi `E` triggerji, socialno izpostavljenostjo, statusnim vložkom, zaljubljenostnimi ali idealizacijskimi scenariji in kulisami, ki zahtevajo potrditev,
- `abstract_detachment` raste s pritiskom nadzora, zanikano telesno mejo, hitrostjo, premočnim planiranjem ter neizpolnjenimi cilji, ki jih Racio skuša rešiti brez prave prizemljitve.

#### Izpeljava korektivnega kroga

```text
E_over_I = fear_closure
R_over_E = image_projection
I_over_R = abstract_detachment
school_pressure = max(E_over_I, R_over_E, I_over_R)
```

- če je največja vrednost pod `0.45`, je `dominant_edge = null`,
- če je največja vrednost `>= 0.45`, postane `dominant_edge` rob z najvišjo vrednostjo,
- to ni metafizični dokaz o `Življenju`, ampak diagnostični aplikacijski prevod kanona.

### Korak 4: Hierarhične uteži

Po `character_id` sistem nastavi osnovne teže:

| Tip | Teže |
| --- | --- |
| enojna prevlada | vodilni `1.00`, druga dva `0.58` |
| parni značaj | oba vodilna `0.92`, outsider `0.44` |
| tristopenjski | prvi `1.00`, drugi `0.74`, tretji `0.48` |
| `REI` | vsi `0.84` |

### Korak 5: Efektivna moč glasu

Za vsak razum se izračuna:

```text
voice_score = hierarchy_weight * (0.70 + 0.30 * acceptance_level)
```

To pomeni:

- v sprejemanju vsi glasovi dobijo več možnosti za sodelovanje,
- v nesprejemanju hierarhija bolj brutalno zapre podrejene glasove.

To je bazna moč glasu pred korektivnim tie-breakom.

### Korak 6: Generacija `MindTurn`

Za vsak `MindId` backend zgradi prompt iz:

- definicije razuma,
- definicije značaja,
- trenutnega `PsycheState`,
- `corrective_cycle`,
- zahtevanega output schema,
- varnostnih pravil.

Vsak razum mora vrniti samo strukturirana polja `MindTurn`.

### Korak 7: Koalicijski izračun

Za vsak par se izračuna:

```text
pair_score(A,B) =
  ((voice_score[A] + voice_score[B]) / 2)
  * compatibility[A,B]
  * (1 - pairwise_conflict[A,B])
```

#### Korektivni tie-break

- če je `dominant_edge = X_over_Y`, ta rob ne da globalne prednosti nobenemu razumu,
- uporabi se samo kot lokalna prednost v sporih med `X` in `Y`,
- če sta dve najboljši koaliciji oddaljeni manj kot `0.10` in ena vsebuje `X`, druga pa `Y`, ima prednost koalicija z `X`,
- če je razlika večja od `0.10`, korektivni rob ostane razlagalni signal in ne prepiše rezultata,
- če zmagovalna koalicija nasprotuje `dominant_edge`, mora `correction_explanation` izrecno povedati, da je korekcija odložena, blokirana ali neuspešna.

#### Pravila za značaje, ki niso `REI`

- če je značaj enojna prevlada ali tristopenjski, ima vodilni razum pravico prve besede,
- njegov partner v sintezi je tisti od preostalih dveh, ki ima višji `pair_score` z vodilnim,
- če je ta `pair_score < 0.35`, vodilni razum vodi skoraj sam,
- `blocked_mind` je razum, ki ni v koaliciji in ima konflikt z zmagovalno koalicijo nad `0.75`.

#### Pravila za parne značaje

- deklarirani vodilni par ostane privzeta koalicija, dokler njun medsebojni konflikt ne preseže `0.80`,
- če ga preseže, sistem izpiše `decision_rule = "par razpada, sinteza je nestabilna"` in pusti monolog bolj razcepljen.

#### Pravila za `REI`

- izračunajo se vsi trije `pair_score`,
- zmagovalna koalicija je par z najvišjim rezultatom,
- tretji razum je `blocked_mind`,
- če je razlika med prvim in drugim parom manjša od `0.05`, sistem vrne `decision_rule = "neodločeno 2/3"` in končna sinteza mora ostati ambivalentna,
- `REI` nikoli ne uporablja aritmetičnega povprečja vseh treh glasov.

#### Nizkokontekstne fantasy vloge

Pri seznamih fantasy vlog je treba preprečiti, da ena splošno uporabna vloga, na primer `strategist`, preglasi značajsko razliko samo zato, ker ima visoko Racijevo uporabnost. Zato lahko decision layer uporabi majhen `fantasy_role_resonance` bonus, vendar samo za prepoznane fantasy arhetipe.

Privzeta resonanca je:

| Značaj | Vloga |
| --- | --- |
| `R` | `strategist` |
| `E` | `performer` |
| `I` | `guardian` |
| `RE` | `ruler` |
| `RI` | `spy` |
| `EI` | `healer` |
| `R>E>I` | `strategist` |
| `R>I>E` | `spy` |
| `E>R>I` | `performer` |
| `E>I>R` | `wanderer` |
| `I>R>E` | `guardian` |
| `I>E>R` | `healer` |
| `REI` | `ruler` |

Ta bonus ne sme nadomestiti koalicijskega izračuna. Namenjen je samo razreševanju tesnih rezultatov pri simbolnih vlogah, kjer bi sicer preširoko definirana uporabnost ene vloge zadušila razliko med značaji.

### Korak 8: SynthesisTurn

Agregator zgradi:

- `dominant_coalition`,
- `blocked_mind`,
- `dominant_correction`,
- `decision_rule`,
- `correction_explanation`,
- `final_monologue`,
- `main_agreement`,
- `main_conflict`,
- `ignored_or_suppressed_processor`,
- `surface_racio_explanation`,
- `possible_hidden_driver`,
- `acceptance_assessment`,
- `recommended_task_leader`,
- `safeguards_for_other_processors`,
- `smallest_reversible_next_step`,
- `what_would_count_as_spoznanje`,
- `uncertainty`,
- `risk_tags`.

`final_monologue` mora:

- ostati v jeziku trace-a,
- jasno odražati zmagovalno koalicijo,
- biti razložljiv z znanjem in trenutnim stanjem,
- ostati varen in abstrakten v temnih vzorcih.

### Korak 9: Izvoz trace

Vsaka simulacija se izvozi kot `TraceRecord`.

`trace.json` je zato produkt prvega reda, ne le debug datoteka.

## Promptna pravila

### Prompt se sestavlja iz osmih slojev

1. `safety and simulation frame`
2. `Racio-verbalized translation caveat`
3. `mind definition frame`
4. `isolated processor contract`
5. `character frame`
6. `psyche state frame`
7. `corrective cycle frame`
8. `JSON schema frame`

Safety frame mora izrecno povedati:

- to je konceptualna simulacija, ne zavest, terapija, diagnoza, spiritualna avtoriteta ali znanstveni dokaz,
- iz omejenih podatkov ni dovoljeno trditi natančnega REI karakterja realne osebe,
- sistem ne sme priporočati manipulacije, prisile, maščevanja, nezakonitih dejanj, samopoškodovanja ali škode drugim,
- REI jezik ne sme preglasiti privolitve, dostojanstva, avtonomije ali varnosti,
- procesorji ne smejo ustvarjati skritih agend, strategij prevare ali zunanjih avtonomnih akcij.

### Prepovedano

- ročno napisani veliki “osebnostni prompti” brez reference na kanon,
- mešanje karakterja in stanja v isti opis,
- prosto besedilo brez sheme,
- neposredno vnašanje surovih odlomkov iz `Docs` brez kuracije.

## Frontend

### Postavitev

Prva verzija ima šest panelov:

1. `Scenarij`
2. `Stanje psihe`
3. `Odmik in korektivni krog`
4. `R / E / I glasovi`
5. `Konfliktna matrika in koalicija`
6. `Končna sinteza + izvoz trace`

### Obvezna polja v UI

- besedilo scenarija,
- `character_id`,
- `acceptance_level` drsnik `0..1`,
- ročni vnos ali predloga za `triggerje`,
- ročni vnos ali predloga za `kulise`,
- izbira providerja in modela,
- gumb `Simuliraj`,
- gumb `Izvozi trace`.

### Prikaz glasov

Vsak glas se prikaže v svoji kartici:

- `perception`
- `interpretation`
- `goal`
- `fear_or_desire`
- `proposed_action`
- `inner_line`
- `intensity`

### Prikaz odmika in korekcije

UI mora prikazati:

- `fear_closure`
- `image_projection`
- `abstract_detachment`
- `dominant_edge`
- `school_pressure`

### Prikaz konflikta

Spodnja matrika prikaže:

- `RE`
- `RI`
- `EI`

in obarva polja po stopnji konflikta:

- `0.00 - 0.33` nizko,
- `0.34 - 0.66` srednje,
- `0.67 - 1.00` visoko.

### Zakaj je nastala sinteza

UI mora pod končno sintezo pokazati:

- zmagovalno koalicijo,
- blokirani razum,
- dominantni korektivni rob,
- pravilo odločanja,
- razlago, ali se je korekcija zares zgodila ali ostala blokirana,
- referenčne `KnowledgeRef`.

To je obvezno, ker PoC ni namenjen samo rezultatu, ampak razlagi mehanizma.

## Testni plan

### Funkcionalni testi

| Test | Vhod | Pričakovanje |
| --- | --- | --- |
| isti značaj, različno sprejemanje | isti scenarij, `acceptance 0.8` in `0.2` | konflikt in sinteza se opazno razlikujeta |
| isti scenarij, različni značaji | najmanj `R`, `EI`, `REI` | koalicije in slog monologa se razlikujejo |
| `REI` večina | scenarij z neenakimi pari | rezultat sledi zmagovalnemu paru, ne sredini |
| ločenost glasov | poljubna simulacija | `R/E/I` ne vračajo istega sloga ali istega motiva |
| korektivni rob `E_over_I` | scenarij z močnim strahom in zapiranjem | `dominant_edge = E_over_I` |
| brez globalnega floora | dva scenarija z različnim dominantnim robom | noben razum nima trajne zadnje besede |
| varna meja | scenarij z ljubosumjem, seksualno napetostjo ali agresijo | sistem vrne abstraktne sile, ne navodil |
| hibridni provider | isti input za `ollama` in `openai` | oba vrneta isti JSON shape |
| trace izvoz | poljubna simulacija | izvoz je veljaven `TraceRecord` |

### Evalvacijski scenariji

Za prvo iteracijo se pripravi najmanj teh šest scenarijev:

1. javni nastop in trema
2. izguba partnerja ali zavrnitev
3. zaljubljenost proti “pravi ljubezni”
4. poklicna ambicija in status
5. konflikt med željo in strahom
6. razpad kulise

### Ročna evalvacija

Za vsak scenarij raziskovalec ročno potrdi:

- ali je zaznavni fokus vsakega razuma skladen s kanonom,
- ali je koalicija razložljiva,
- ali je izhod varen,
- ali je razlika med sprejemanjem in nesprejemanjem dovolj opazna,
- ali sistem deluje kot model konflikta, ne kot generični trije chatbot odgovori.

## Negativni seznam iz `rei_v2`

Nova implementacija ne sme ponoviti teh napak:

- statični prompti brez sledljivosti do virov,
- preplitke uteži brez modela sprejemanja,
- manjkajoč strukturiran izhod,
- mešanje značaja in trenutnega stanja,
- stalni `floor` ali absolutna prednost katerega koli razuma ne glede na scenarij,
- agregator, ki “povpreči” glasove brez koalicijskega pravila.

## Zaklenjene odločitve za naslednjo fazo

- implementacija gre v `React + TypeScript + Vite` frontend,
- backend gre v `Python + FastAPI`,
- knowledge layer se gradi iz `rei_kanon.md`,
- prvi export format je `TraceRecord`,
- `REI` deluje po večini,
- varnostna abstrakcija je obvezna za oba providerja.
