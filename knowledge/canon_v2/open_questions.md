# REI Native Composition Canon v2 — odprta vprašanja

Status: `open_questions`
Canon language: Slovenian
Operational gloss language: English
Runtime effect in B1: none

Ta register je normativen glede negotovosti: zapisano vprašanje ni dejstvo in
ni dovoljenje, da ga implementacija, evaluator ali model zapolni s prikrito
hevristiko. Če poznejša faza sprejme začasno rešitev, jo mora označiti kot
`implementation_hypothesis`, povezati s claim ID-jem in ohraniti možnost
zamenjave.

## OQ-SCHEMA-001 — serializacija, ID-ji, čas in hashi

Odprti so skupna artifact `schema_version`, format stabilnih ID-jev in časovnih
žigov, kanonična JSON serializacija ter algoritmi za `scene_hash`,
`immutable_hash` in hash posameznega `EgoMeasure`. B2 mora izbrati eno
reproducibilno pogodbo pred pisanjem modelov in fixtureov.

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, operativno razrešeno za B2 in zamenljivo
ob novi arhitekturni odločitvi.

- Vsak serializiran artefakt nosi eksplicitni `schema_version` in domensko
  poimenovani stabilni ID, na primer `event_id`, `bundle_id` ali `measure_id`.
- Izpeljani content ID je `{prefix}_{32 lowercase SHA-256 hex znakov}`;
  zunanji ID-ji ostanejo dovoljeni, če so nespremenljivi in sledljivi.
- Časovni žigi so timezone-aware UTC `datetime`; kanonična serializacija jih
  zapiše kot RFC 3339 z mikrosekundami in končnico `Z`.
- Kanonični JSON je UTF-8, ohrani Unicode, uredi object ključe, uporablja
  kompaktna ločila, prepove `NaN`/neskončnost in ohrani vrstni red seznamov.
- `scene_hash`, `immutable_hash` in hash `EgoMeasure` so polni lowercase
  SHA-256 heksi kanoničnih payloadov; samo lastno hash polje se izloči iz
  njegovega preimagea.
- Konceptualni `dict` zapisi iz plana se v Pydantic pogodbah predstavljajo kot
  tuple poimenovanih entry modelov (`AttentionWeight`, `ValuationDimension`,
  `BodyDelta`, `MindOption`, `MindStatement`, `ProviderParameter`). Tako so
  podvojeni ključi zavrnjeni, vrstni red pa je kanoničen in hash-reproducibilen,
  namesto da bi bil odvisen od vrstnega reda vhodnega JSON objekta.

Ta pogodba je programska operacionalizacija, ne Erosova ali izvorna trditev.

## OQ-PROVIDER-001 — provenance, timeout in fallback pogodba

Plan zahteva sledljive provider/model klice, vendar ne določa ene dokončne
sheme za identiteto implementacije, parametre, timeout in odsotnost
kompatibilnega fallbacka.

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, operativno razrešeno za B2. Identiteta
providerja vedno beleži implementacijo in njeno revizijo; model-backed
provider dodatno zahteva model, model revision in seed. Parametri se hranijo
kot poimenske kanonične JSON vrednosti. Vsak call spec ima pozitiven timeout
ter eksplicitni `ProviderFallbackPolicy`: bodisi vnaprej določen sekundarni
provider bodisi `mode="none"` z ne-praznim razlogom. Call record se veže na
hash prvotnega speca, beleži konec primary poskusa in ne sme uvesti
nenačrtovanega fallbacka. Uspešen in neuspešen fallback sta reprezentabilna;
načrtovani fallback po neuspešnem primary poskusu mora imeti izvedbeni outcome
ali eksplicitni `skipped` zapis z razlogom;
failed ali timed-out poskus ne sme objaviti končnih output artefaktov in ne sme
podpirati result artefakta; result mora ustrezati tudi capability kindu providerja.
Ker so artefakti immutable, isti artifact ID ne sme biti hkrati input in output
istega provider klica.
Artifact-store sprejme samo kanonične portable poti
relativno na run root. Končna izbira konkretnih providerjev ali modelov ostaja
zunaj B2.

## OQ-RANGE-001 — območja confidence in intensity

`BodyState` je predlagan v območju `[0, 1]`, za druga polja confidence,
intensity, fidelity in valuation pa plan ne določa popolne semantike,
kalibracije ali obravnave manjkajoče vrednosti. Ne predpostavljaj, da
confidence pomeni značajsko avtoriteto.

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, delno razrešeno samo na ravni podatkovne
pogodbe. Normalizirani score-i v B2 uporabljajo zaprto območje `[0, 1]`, ne
sprejemajo `NaN` ali neskončnosti in manjkajoče vrednosti ne pretvorijo tiho v
nevtralno oceno. Njihova empirična kalibracija ostaja odprta. Noben score,
vključno z availability, confidence ali intensity, ne spremeni strukturnega
karakterja ali authority tierov. `BodyDelta` in asociacijski delta zapisi
uporabljajo območje `[-1, 1]`; to je podatkovna normalizacija, ne fiziološka
trditev.

## OQ-NATIVE-001 — dokaz neodvisne procesorske poti

Kateri kratek, opazljiv dokaz pokaže, da so R, E in I do sklepa prišli po
lastnih poteh, ne da bi sistem zahteval ali razkrival dolgo skrito verigo
razmišljanja? Kandidati so provenance evidence ID-jev, nativni artefakti,
route tags in kratek decision bridge.

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, delno razrešeno. Vsak nativni sklep nosi
`source_packet_id` in `source_scene_id`; `NativeMindBundle` zavrne sklepe iz
drugačnega dogodka in option ID-je zunaj `SceneEvent`. Bundle shrani samo
sortirane dovoljene option ID-je, tri source-packet hashe, scene hash, ID/hash
Emocio visual state, ID/hash začetnega Instinkt BodyState, hashe Instinkt
rolloutov in lasten immutable hash; po deserializaciji znova preveri membership.
`validate_packets(scene=...)` znova zapre packet-to-scene evidence scope,
`validate_native_lineage(...)` pa vse kompaktne reference primerja z zaupanja
vrednimi intermediate artefakti. `RunManifest` pri direct runu dodatno veže tri
provider output zaključke na eksplicitni deterministični bundle-assembly zapis.
Vsak sestavljeni native zaključek ima natanko en successful provider call kot
producenta, zaključenega pred začetkom assembly koraka; bundle ID sme proizvesti
samo assembly. `native_artifact_source` izrecno loči lokalno `produced` od
`inherited`; slednji zahteva parent ID/hash in zunanjo primerjavo vseh štirih
native hash zapisov z natančnim parent manifestom, ki se je zaključil pred
začetkom child runa.
Dokaz kakovosti
dejansko neodvisne procesorske poti ostaja predmet poznejših evaluatorjev.
Vsak tip nativnega sklepa dodatno izpostavi `validate_against(packet)` mejo;
Emocio jo razširi na structured visual state, Instinkt pa na začetni BodyState
in decisive rollout. Dejanski processorji morajo te meje uporabiti v poznejših
fazah.

## OQ-RACIO-001 — RacioInputPacket

Plan opisuje Racijev vhod semantično, ne pa z dokončno shemo. B2 mora določiti
minimalna polja, pri čemer profil, rang in skriti E/I motivi v kontroliranem
načinu ostanejo prepovedani.

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, operativno razrešeno za B2. Paket vsebuje
simbolno-jezikovne in številčne cue, dejstva in neznanke, čas, pravila,
eksplicitne možnosti in posledice, omejitve, dovoljene option ID-je, evidence
ID-je, `RacioWorld`, reference na prejšnje `RacioProjection` zapise ter caveat.
Profil, authority tier in skriti E/I motivi niso polja paketa.

## OQ-TRANSLATION-001 — zvestoba Racijevega prevoda

Kako evaluator loči uporaben prevod od opustitve, racionalizacije,
minimizacije, projekcije ali napačne klasifikacije? `TranslationGap` ne sme
postati ground-truth namig Raciju in ne sme zahtevati razkritja chain-of-thought.

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, delno razrešeno na ravni provenance.
`ManifestationObservation` loči običajno manifestirano vsebino od
`renderer_added_ungrounded`; samo slednja sme citirati generated image ID.
`EmocioManifestation.validate_against(...)` preveri, da vidne slike izvirajo
iz scene pripadajočega frozen native zaključka. `RacioInterpretation` nato
preveri še ujemanje source-mind tipa, manifestation ID-ja in to, da je citirana
renderer-added slika res vidna v isti Emocio manifestaciji. Merilo kakovosti
prevoda ostaja odprto.

## OQ-EMOCIO-001 — vizualna valuation in renderer

Katere valuation dimenzije so dovolj stabilne za prvi Emocio PoC in kako se
kalibrirajo? Kdaj je renderer samo vizualizacija in kdaj legitimni del
manifestacije? Končni model/provider ni izbran. Pred kakršnimkoli generiranjem
slik je potrebna uporabnikova izrecna potrditev.

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, delno razrešeno. `ImageArtifact` sprejme
veljaven `image/*` MIME tip ter beleži request/call/spec ID-je, provider,
seed, input in content hash, prompta, mere in generated-only elemente;
model/revizija sta obvezna skupaj samo za model-backed renderer, da ostane
dovoljen tudi `NullImageRenderer`. `grounded` je tipovno vedno `false`.
Image in grounded-mask poti uporabljajo isti portable relative-path kontrakt kot
artifact store.
Za transparenten B2 podatkovni kontrakt ima vsak option rollout kanonično
urejenih 11 dimenzij iz §10.7 (začenši z `desired_scene_match`), native zaključek pa mora ohraniti valuation
izbranega decisive rollouta. Imena in `[0, 1]` območje so zamenljiva
operacionalizacija; uteži, agregacija in empirična kalibracija ostajajo odprte.
`EmocioVisualState` citira source scene in packet, option rollouti ter njihove
valuation vrstice pa so kanonično urejeni po option ID-ju.
Renderer, končni model in dovoljenje za dejansko generiranje slik prav tako
ostajajo odprti.

## OQ-INSTINKT-001 — virtual-body dinamika

Katera minimalna deterministična dinamika zadostuje za nevarnost, izgubo,
meje, zaupanje, navezanost, pomanjkanje in okrevanje, ne da bi predstavljala
medicinski ali fiziološki model? Vsa sprejeta pravila morajo ostati vidna v
`instinkt.yaml` in označena po statusu.

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, delno razrešeno samo na ravni sheme in
lineage. `InstinktInputPacket` citira začetni `BodyState`; native zaključek
ohrani isti source body-state ID ter po potrebi decisive rollout ID in option
ID. `BodyTransition` zahteva popoln in numerično skladen seznam spremenjenih
dimenzij, unikatne evidence ID-je in prepove različni vsebini z istim stabilnim
BodyState ID-jem. Isto pravilo velja znotraj rollout trajectory; rollout ID-ji in
option ID-ji so unikatni, vsak packet option pa ima rollout, ki se začne v
zaupanja vrednem source BodyState. Triggering evidence BodyTransitiona mora
ostati znotraj evidence scope pripadajočega Instinkt input packeta. Konkretna
deterministična dinamika in pragovi ostajajo za B8.

## OQ-PAIR-001 — spor dveh enakovrednih vodilnih razumov

Pregledani viri ne dajejo univerzalnega pravila za vsak spor vodilnega para.
Začetna runtime politika `unresolved` in omejeni informacijski pogajalski krog
sta izvedbeni hipotezi; podrejeni razum, Racio, confidence ali LLM niso
samodejni tie-breakerji.

### B3 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, delno razrešeno. Osnovni resolver zapiše
nesoglasje vodilnega para kot `unresolved`; podrejeni razum ne razreši spora.
Pogajalski krog je omejen na največ dve zaporedni dodatni iteraciji. Vsaka mora
imeti nov information ID ali rollout ID, ponovna uporaba iste provenance pa ni
nova informacija. Konvergenca obeh vodilnih razumov po takem krogu je dovoljena;
univerzalno pravilo, ki bi ju prisililo v konvergenco, še vedno ne obstaja.

## OQ-DELEGATION-001 — delegacija, nadomeščanje in odsotnost stališča

Kateri minimalni podatki ločijo prostovoljno delegacijo, začasno operativno
nadomeščanje, funkcionalno omejitev, `abstain_no_view`, `unknown`,
`unavailable` in močan signal podrejenega razuma? Nobena kategorija sama po
sebi ne spremeni strukturnega karakterja.

### B3 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, delno razrešeno. Delegacija je veljavna
samo kot ekspliciten `TaskDelegation` vseh trenutno vodilnih razumov k drugemu,
funkcionalno prisotnemu razumu. Delegirana možnost mora biti njegov nenull
nativni sklep in ostati v scopeu zamrznjenega bundlea. Strukturni ter učinkoviti
tieri se ne spremenijo, že razrešene možnosti pa delegacija ne zamenja.
Nerešen `PairConflict` ostane zabeležen. B3 zavrne
hkratno delegacijo in funkcionalni override, ker en sam status mandata ne more
pošteno predstavljati obeh mehanizmov.

## OQ-AVAILABILITY-001 — prag funkcionalnega overridea

Kdo ali kaj lahko razglasi funkcionalno nedostopnost, pri katerem pragu in s
kakšnim dokazom? `override_reason` mora biti ekspliciten; stres, strah, mood,
keyword ali confidence niso zadosten razlog.

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, delno razrešeno. Sprememba
`EffectiveAuthority` zahteva `FunctionalOverride` z razlogom
`explicit_functional_unavailability`, natančnim seznamom odstranjenih razumov,
snapshotom availability in evidence ID-ji. Kdo razglasi nedostopnost in pri
katerem pragu, ostaja odprto; model je ne sklepa sam iz scorea.

### B3 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, delno razrešeno. `EffectiveAuthority` se
izračuna iz eksplicitnega seznama `unavailable_minds`; numerične availability
vrednosti nimajo implicitnega praga in ne vplivajo na razvrstitev. Če override
odstrani vse tri razume, resolver vhod zavrne namesto izmišljanja prazne ali
četrte avtoritete.

## OQ-CONCLUSION-IDENTITY-001 — primerljivost nativnih sklepov

Kako dolgoročno dokazati, da modalno različni native procesorji niso izbrali le
istega opaznega dejanja, temveč isti sklep? B3 kot začetni primerjalni ključ
uporablja nenull `NativeConclusion.option_id`, ker predstavlja izbiro sklepa
pred `ConsciousDecision` in `BehaviorResultant`. Sam `BehaviorResultant` ni
vhod v governance ali spoznanje. To je izvedbena hipoteza; prihodnji bogatejši
proposition oziroma conclusion-identity zapis jo lahko nadomesti brez
spreminjanja ordinalnih pravil. Vsaka abstinenca povzroči `unknown` oceno
spoznanja; `None` ni glas in `None = None` ni konvergenca.

## OQ-ACCEPTANCE-001 — merjenje sprejemanja

Kako iz omejenih podatkov zanesljivo oceniti vidnost, zvestobo prevoda,
toleranco, pripravljenost na delegacijo in tveganje sabotaže? Do pregledanega
merila je AcceptanceState v kontroliranih simulacijah ekspliciten vhod, ne
keyword classifier.

## OQ-ACCEPTANCE-002 — meja med nestrinjanjem in nesprejemanjem

Kateri dokaz loči vsebinsko nestrinjanje ob dobrem sodelovanju od preslišanja,
popačenja ali sabotaže? Enaka zunanja izbira prav tako ni zadosten dokaz
sprejemanja.

## OQ-BEHAVIOR-001 — začetna vedenjska tabela

Natančna deterministična tabela med acceptance mode, mandatom, Racijevo
interpretacijo, ConsciousDecision in BehaviorResultant še ni potrjena.
Ohraniti mora razhajanja in ne sme v enem `integrated_decision` stavku skriti
delay, oscillation, sabotage, blocked ali unresolved.

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, delno razrešeno samo na ravni sheme.
Mandatna in zavestna poravnava uporabljata `aligned`, `diverged`, `unknown` ali
`not_applicable`; tabela, ki iz teh stanj izpelje vedenje, ostaja za B10.

## OQ-EGO-001 — kanonična in opisna polja Ega

Katera polja `EgoMeasure` in `EgoCompositionSnapshot` so nujna arhitekturna
jedra ter katera samo uporabne opisne projekcije? Source-supported je meja, da
Ego ni četrti razum; Measure/Trace/Snapshot so izvedbena operacionalizacija.

## OQ-EGO-002 — izračun kompozicijskega posnetka

Kako se iz append-only sledi reproducibilno izračunajo motivi, konflikti,
prevodne napake, razrešene in nerazrešene napetosti, commitmenti in trenutni
»odsek skladbe«? Vsaka izpeljava mora navesti `evidence_measure_ids`.

## OQ-PROJECTION-001 — projekcije zgodovine trem razumom

Kakšne so dokončne sheme in pravila posodobitve za RacioProjection,
EmocioProjection in InstinktProjection? Projekcija sme vplivati na naslednji
svet/spomin, ne pa izreči četrtega mnenja ali retroaktivno spreminjati tracea.

## OQ-PERSON-001 — dokončne komponente PersonState

Arhitekturna meja zahteva, da oseba ni reducirana na karakter, vendar B1 še
ne določa dokončnih shem za `MindDevelopment`, `MindWorlds`, `CurrentState`,
`EgoComposition`, `FunctionalOverride`, `TaskDelegation` in `OutcomeRecord`.
B2 jih mora definirati brez združevanja strukturnega karakterja in stanja.

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, delno razrešeno. Začetni `PersonShell`
gnezdi `CharacterAuthority`, `MindDevelopment`, `MindWorlds`,
`AcceptanceState` in `CurrentState`, prazno ali nastajajočo Ego sled naslovi z
`ego_id`, izpeljani snapshot pa z opcijskim `ego_composition_id`. Tako genesis
stanje ne potrebuje izmišljenega measurea. Razmerje do trajnega storea in
lifecycle posameznega runa ostaja odprto.

## OQ-LIFE-001 — metafizična meja Življenja

Odnos med Egom in pojmom Življenja ostaja ločeno raziskovalno področje.
Trenutni sistem nima operativne definicije njegove avtoritete, zato ne
implementira `LifeAgent`, `LifeDecision` ali `LifePrompt`.

## OQ-SAFETY-001 — javni safety caveat

Kakšna bo dokončna shema, lokalizacija in propagacija javnega opozorila, da je
izdelek konceptualni simulator po teoriji REI, ne diagnoza, empirično potrjena
psihologija ali karakterizacija resnične osebe?

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, delno razrešeno. Tip `SafetyNotice`
tipovno zaklene oznake `conceptual_simulator=true`,
`diagnostic_use_allowed=false` in
`real_person_characterization_allowed=false`; obvezen je v run manifestu in
provider call pogodbah. Natančna predstavitev v prihodnjem API-ju in GUI ostaja
odprta.

## OQ-NAMING-001 — pogodbeno poimenovanje

Pred B2 je treba poenotiti `VisualSituationPacket`/`EmocioInputPacket` in
`InstinctAssociation`/`InstinktAssociation`. Za testni slikovni adapter je B1
sprejel ime `NullImageRenderer`. Slovenski izraz Instinkt ostane kanoničen,
angleški JSON ključi pa so lahko operativni.

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, operativno razrešeno za B2. Pogodbeni
imeni sta `EmocioInputPacket` in `InstinktAssociation`; `NullImageRenderer`
ostaja rezervirano ime poznejšega testnega adapterja.

## OQ-KULISA-001 — meja izraza kulisa

Izraz potrebuje širši source sweep pred strojno klasifikacijo. Do takrat je
definicija konservativna in izraza ni dovoljeno uporabiti kot splošno oznako
za navado, laž ali psihološko diagnozo.

## OQ-LEGACY-001 — prikaz legacy uteži

Kako arhivske decimalne uteži prikazati v primerjalnih poročilih brez
preslikave nazaj v aktivno governance? Migracija poročil ne sme uteži,
situacijskih bonusov ali benchmark pravil vrniti v odločanje.

## Izrecno zaprte smeri, ki niso odprta vprašanja B1

- QLoRA, LoRA, SFT, training dataset in izbor končnega modela niso v obsegu.
- Ego ni četrti agent ali odločevalec.
- Generirana slika ne ustvarja grounded evidence.
- Decimalne uteži, keyword sprejemanje in situacijski override niso dovoljena governance pravila.
- Psihološka diagnoza, karakteriziranje resničnih oseb in medicinske trditve niso cilj sistema.
