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

### B5 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, operativno razrešeno za native Racio.
Aktivni builder izdela content-addressed, profile-blind packet, ga veže na hash
točnega `SceneEvent` ter ohrani vrstni red eksplicitnih dejstev, neznank,
možnosti, omejitev in evidence ID-jev. Dejstva lahko izvirajo samo iz supplied,
grounded evidence ali iz eksplicitnega `RacioWorld`; vsako uporabljeno supplied
dejstvo mora citirati pripadajoči evidence ID. Dejstva, neznanke in kavzalni
koraki so ločena, neprekrivajoča se polja.

`DeterministicRacioProvider` je infrastrukturni fixture z javno politiko
`first-allowed-option-v1`; ne uporablja semantičnega ali keyword vrednotenja in
ni nadomestek za produkcijski reasoner. `TextReasonerRacioAdapter` sprejme samo
strogi JSON, zapre provider call/result ID in hash ter zavrne neznana dejstva,
možnosti, evidence ali dodatna polja. Konkreten LLM ni izbran. Interpretation,
commit in narration niso del B5 ter ostajajo ločene poznejše faze.

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

### B9 dokumentacijska odločitev — 2026-07-13

Status: `implementation_hypothesis`, pogodba in omejeni B9 runtime sta
implementirana. Konsolidirani contract je `knowledge/canon_v2/communication.yaml`.

RacioInterpreter sme prejeti samo zamrznjene E/I manifestacije, strukturirane
opazke in izrecno javni option scope. Ne sme prejeti `NativeMindBundle`, E/I
native sklepa, `TranslationGap`, native motive summaryja, hidden motive,
karakterja, authority tierov ali diagnostičnega distortion labela. Gap izdela
ločen evaluator šele po interpretaciji. Interpreter validation napačne
interpretacije ne sme popraviti z native ground truthom.

Za reproducibilne B9 fixture teste je sprejeta binarna, ne-semantična metrika
`b9-exact-action-tendency-fidelity-v1`. Ima natanko eno tipizirano komponento
`action_tendency` z utežjo `1.0`: rezultat je `1.0` samo ob natančni enakosti
native in interpretirane action tendency, sicer `0.0`. Ne normalizira ali
semantično primerja prostega besedila. Obstoječe polje `motive_fidelity` samo
zrcali rezultat te komponente; native motive summary in interpretirani motive
sta diagnostična zapisa in ne trditev o semantični zvestobi motiva.

Začetni `b9-exact-distortion-classifier-v1` označi status `omitted_b9` ali
`unavailable_b9` kot `omission`; dva `None` option ID-ja kot `unknown`; exact
nenull option in exact action tendency kot `none`; option mismatch ali
action-tendency rezultat `0.0` kot
`misclassification`; vse drugo kot `unknown`. `rationalization`,
`minimization` in `projection` se brez dodatnega eksplicitnega evaluator
evidencea ne sklepajo. Keyword classifier je prepovedan.

Interpretirani `None` pomeni samo, da Racio ni sklepal optiona; ni provider
failure, dokaz native abstinence ali visoke fidelity. Če sta oba option ID-ja
`None`, B2 `option_match` zaradi tehnične enakosti ostane `true`, semantična
primerjava optiona pa je `not_applicable` in sama ne dokazuje uspešnega prevoda.
Za obstoječ evaluated comparison zato pomeni distortion `unknown`; status
`omitted_b9` ali `unavailable_b9` ostane `omission`. Provider failure je ločen
attempt outcome brez `RacioInterpretation` result artefakta.

Emocio projection, strukturirani vrstni red observations, scripted no-provider
fixture, content ID/hash lineage, action-tendency metrika, native motive summary
in zgornji classifier
so javno poimenovane izvedbene hipoteze v communication kanonu. Noben konkreten
interpreter model/provider ni izbran; B9 dokumentacija ne kliče lokalnega LLM,
GPU-ja ali modela. Empirična kalibracija confidence, delne/semantične motive
fidelity in dokazovanje racionalizacije zato izrecno ostajajo odprti v tem OQ.

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

### B6 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, operativno razrešeno za structured core.
Deterministični router sprejme samo grounded `image`, `video` in `body`
modalitete, ne uporablja tekstovnega keyword/sentiment klasifikatorja ter packet
content-addressed veže na hash dogodka. Compiler ohrani isto identiteto in isti
grounded evidence scope v current, desired, broken in vseh option-rollout
scenah; svetovni spomini, želeni/broken elementi in option opisi so izrecno
`inferred_elements`.

Začetni valuator uporablja natančno ujemanje strukturiranih atomov. Manjkajoča
referenca dobi nevtralno vrednost `0.5`, vseh 11 dimenzij se zaokroži na šest
decimalk in enakovredno aritmetično povpreči. Izbrana je samo enolična najvišja
vrednost; pri natančnem tieju Emocio abstinira. Začetna action tendency izbrane
možnosti je `approach`. To je nekalibrirana fixture politika, ne empirična
trditev. `NullRenderer` je implementiran, native conclusion pa nastane pred
vsakim opcijskim renderjem. B6 ni generiral nobene slike; konkreten lokalni
renderer, img2img in model ostajajo B7.

### B7 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, operativno razrešeno za opcijsko lokalno
renderiranje brez izbire končnega modela. `LocalEmocioRenderer` iz vsakega
zamrznjenega `VisualSceneSpec` izdela content-addressed `ImageRenderRequest` in
ga prek obstoječe provider meje preda `DiffusersImageRenderer`. Zahtevek,
`ProviderCallSpec`, `ProviderCallRecord`, dejanski PNG in `ImageArtifact` so
vezani z ID-ji ter hashi; ID slike je funkcija request ID-ja in SHA-256
dejanskih bajtov. Store pred objavo preveri PNG podpis, dimenzije, portable pot,
atomarni zapis in ponovno prebrani hash. Pri img2img pred klicem ponovno preveri
še source path/hash/dimenzije. T2I prepove source/strength, img2img ju zahteva in
v začetni pogodbi ohrani source dimenzije.

Vsi numerični render parametri so eksplicitni vhodi; B7 ne uvede privzetih
dimenzij, korakov, guidance ali strength. Eksplicitni root seed se za vsako
sceno deterministično izpelje v 63-bitni seed iz SHA-256 oznake algoritma,
root seeda in source-spec ID-ja; dejanski fallback seed ostane vezan na svoj
provider attempt. Request in call dodatno zapišeta pipeline implementacijo,
njeno revizijo ter dtype/device/load/runtime parametre. Lokalni adapter ne izvede
nenačrtovanega provider retryja; `disabled`, `succeeded`, `partial` in `failed`
so strukturirani batch statusi, neuspeh pa kot varen rezultat ohrani že
zamrznjeni Emociev sklep. Vsak ne-disabled batch mora imeti outcome ali
ekspliciten preparation-failure za vsako source sceno. Prompt compiler samo deterministično izpiše polja
scene in ne ocenjuje ali izbira možnosti.

Adapter zahteva eksplicitni model repository in nespremenljiv 40-mestni hex
Hub commit; runtime sprejme le že lokalno prenesene datoteke, zato download ni
del render klica. Končni slikovni model ostaja odprt. Opcijski stack je
bil 2026-07-13 preverjen proti uradnim stabilnim izdajam: PyTorch 2.13.0,
Diffusers 0.39.0, Transformers 5.13.0, Accelerate 1.14.0, safetensors 0.8.0 in
Pillow 12.3.0. Testi uporabljajo samo deterministični fake backend; B7 med
verifikacijo ne kliče modela in ne generira slike na GPU.

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

### B8 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, operativno razrešeno za prvi omejeni
Instinkt simulator. Spodnja pravila so zamenljiva programska
operacionalizacija; niso empirična psihološka, medicinska ali fiziološka
trditev. Vprašanje njihove empirične ustreznosti zato ostaja odprto.

- `BodyState` ima 13 fiksnih dimenzij iz `instinkt.yaml`; vse so finite v
  `[0, 1]`, tipizirana vhodna `BodyDelta` pa je v `[-1, 1]`.
- Privzeti rollout izvede natanko tri korake; konfiguracija dovoljuje od 1 do
  8. `max_options` je privzeto 16 in omejen na 1–32, packet pa sme imeti tudi
  nič možnosti. Privzeta absolutna per-step meja delte je `0.25` in mora biti
  v `(0, 1]`.
- Za vsako dimenzijo velja
  `step_delta = clamp(effect_delta / rollout_steps, -max_delta, +max_delta)` in
  `next = clamp(previous + step_delta, 0, 1)`. Ni convergence ali
  neskončnega agentnega loopa; replay numeričnih artefaktov uporablja absolutno
  toleranco `1e-12`.
- Vsak packet option potrebuje natanko en vsebinsko naslovljen
  `OptionBodyEffect`. Besedilo dogodka ali cuejev ni keyword/sentiment
  klasifikator in samo po sebi ne ocenjuje možnosti.

Začetni nekalibrirani loss in recovery funkciji sta:

```text
predicted_loss = clamp01(
  0.50*base_predicted_loss
  + 0.15*(1-physical_integrity)
  + 0.10*pain
  + 0.10*tension
  + 0.05*(1-boundary_integrity)
  + 0.05*(1-resource_security)
  + 0.05*(1-attachment_security)
  + 0.20*loss_memory_strength
)

recoverability = clamp01(
  0.50*base_recoverability
  + 0.15*energy
  + 0.10*escape_availability
  + 0.10*predictability
  + 0.05*trust
  + 0.05*attachment_security
  + 0.05*resource_security
  - 0.20*loss_memory_strength
)
```

Jedrne loss, recovery in intensity uteži morajo vsaka zase dati vsoto `1.0`
z absolutno toleranco `1e-12`. `loss_memory_strength` je največji
`retrieval_score` med dejansko vrnjenimi asociacijami z zapisano izgubo, sicer
`0.0`; gola `felt_intensity` ali `effective_strength` torej ne obide kakovosti
exact-token ujemanja.

Asociacijski spomin ima privzeto kapaciteto 32 (dovoljeno 1–256), retrieval
limit 4 (1–32 in največ kapaciteta), minimalno učinkovito moč `0.05` v
`[0, 1]` ter največji advance na klic 10.000 ciklov (konfigurabilen
1–1.000.000; posamezni integer advance je od 0 do te konfigurirane meje,
`bool` pa ni integer vhod).
Tokeni se samo `strip()`/`casefold()` normalizirajo, deduplicirajo in uredijo;
ni tokenizacije, stemminga ali semantičnega classifierja. Velja:

```text
age_cycles = current_cycle - insertion_cycle
effective_strength = clamp01(felt_intensity - decay*age_cycles)
overlap_ratio = exact_overlap_count / unique_signature_token_count
retrieval_score = effective_strength * overlap_ratio
```

Zadetki so urejeni po `retrieval_score` padajoče, nato po
`effective_strength` padajoče in `association_id` naraščajoče. Po preseženi
kapaciteti se odstrani zapis z najmanjšo trenutno učinkovito močjo, nato
najstarejšim insertion indexom in nato `association_id`; podvojen ID je
prepovedan. Vsak match hrani association hash, cikel, starost, overlap, moč in
score, rollout pa njegove kanonične ID-je in celotne zapise.

Zaščitna politika minimizira:

```text
protective_cost = predicted_loss
  + 0.25*(1-recoverability)
  + 0.15*final_tension
  + 0.10*final_uncertainty
```

Privzeti penaltyji dajo vsoto `0.50`, konfiguracija pa prepove vsoto nad
`0.50`; zato je cost v `[0, 1.5]`. Vsi costi z
`abs(cost-minimum) <= tie_epsilon` so izenačeni; privzeti epsilon je `1e-12`
in dovoljen v `[0, 1]`. Dve ali več izenačenih možnosti pomenita
`abstained_tie` brez skritega sekundarnega tie-breakerja. Prazen option set
pomeni `abstained_no_options`, brez scoreov ali decisive rolloutu in z
intenzivnostjo `0.0`.

Za izbrani rollout je native intenzivnost
`clamp01(0.60*predicted_loss + 0.25*final_tension + 0.15*final_arousal)`;
pri tie abstinenci je največja intenzivnost izenačenih rolloutov. Manifestacija
uporabi finalni `BodyState` decisive roll-outa, pri abstinenci pa začetnega, in
izračuna:

```text
felt_tension = tension
fear_intensity = clamp01(0.50*intensity + 0.30*tension + 0.20*arousal)
attachment_pull = clamp01((1-attachment_security)*intensity)
withdrawal_urge = intensity samo za withdraw ali seek_safety, sicer 0
freeze_intensity = intensity samo za freeze, sicer 0
boundary_alarm = clamp01(1-boundary_integrity)
```

Manifestacija je vsebinsko naslovljena in hrani ID/hash sklepa ter BodyStatea;
ob izbiri tudi ID/hash decisive roll-outa, pri abstinenci pa ga ne sme citirati.
Config, typed effect, vsak transition, association match, rollout, policy in
manifestation imajo preverljivo ID/hash lineage. Transition se mora ponovno
izvesti iz effecta in configa, rollout pa mora ponovno dokazati verigo,
asociacije, `predicted_loss` in `recoverability`. Vhod procesorja ne vsebuje
profila ali karakterja, vsi artefakti so frozen, body state in spomin pa ne
smeta spremeniti `structural_character` ali `authority_tiers`.

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

### B9 dokumentacijska odločitev — 2026-07-13

Status: `implementation_hypothesis`, omejeno na record-only audit. Za
interpretacijo E se uporabi samo relacija `R_to_E`, za I pa samo `R_to_I`, ker
je Racio opazovalec vira. Assessment zapiše njen deklarirani
`interpretation_fidelity` ter ID/hash eksplicitnega `AcceptanceState` in
`TranslationGap`; obratni relaciji nista vhod te ocene. B9 ne računa composite
scorea ali thresholda ter z acceptance
vrednostmi ne filtrira observations, ne spreminja script/provider prompta,
optiona, motiva, confidence, translation gapa, governance ali behaviorja.

To ne dokazuje monotonične ali vzročne zveze med `interpretation_fidelity` in
manjšo vrzeljo. Planov `test_high_fidelity_reduces_translation_gap` sme v prvi
fazi pomeniti samo popolnoma razkrit kontrolirani par scripted fixtureov z
vnaprej podanima acceptance states, scriptoma, tipiziranima action tendency in
pričakovanima gapoma. Tak test preveri pipeline in provenance tega para, ne
univerzalne psihološke zakonitosti.
Primernejše natančno ime je
`test_scripted_high_fidelity_fixture_has_smaller_exact_gap`.

### C3 izvedbena odločitev — 2026-07-14

Status: `implementation_hypothesis`, omejeno na zamenljivi
`c3-conscious-access-filter-v1`. C3 prvič uporabi izrecni `AcceptanceState` za
izdelavo modelu vidnega signala, vendar formule ne predstavlja kot empirično
psihološko zakonitost. Za vir E uporabi samo `R_to_E`, za vir I pa samo
`R_to_I`:

```text
suppression = (1 - tolerance) * sabotage_risk
effective_visibility = visibility * (1 - suppression)
signal_fidelity = interpretation_fidelity * (1 - 0.5*sabotage_risk)
signal_noise = 1 - signal_fidelity
delegation_openness = delegation_willingness
channel_quality = effective_visibility *
  (0.70*signal_fidelity + 0.15*tolerance + 0.15*delegation_openness)
```

Vrednosti se omejijo na `[0, 1]`. Filter s content-stabilnim hash rangom in
eksplicitnim seedom izbere `ceil(N*effective_visibility)` opazk; kadar je
vidnost pozitivna, ohrani najmanj eno. Nato je
`ceil(V*signal_fidelity)` izbranih opazk jasnih, ostale pa so označene kot
`degraded` in njihova natančna vrednost je redigirana. Degradacija nikoli ne
obrne signala in ne izmisli konkurenčnega motiva. Pri ničelni efektivni
vidnosti ni vidnih opazk ali vizualnih artefaktov.

Model prejme samo `ConsciousAccessPacket` z lokalnimi opaque aliasi,
deklariranim javnim opisom možnosti, kakovostjo kanala in negotovostjo. Ne
prejme acceptance dimenzij, dejanskih observation/option ID-jev, native
lineage, karakterja ali evaluatorjevega ground trutha. Ločen trusted audit
ohrani popolno preslikavo in uporabljeno formulo. Enaka javna površina ob
različnem skritem native stanju mora dati bajtno enak provider payload; razlikuje
se sme samo trusted audit.

Za C3 benchmark velja dodatna, vnaprej deklarirana kalibracijska hipoteza:
če je odločilni action cue degradiran, izpuščen ali protisloven, interpreter
abstinira pri optionu, za nepodprt action oziroma motive class uporabi
`unknown` in omeji confidence na `0.35`. To je benchmark/runtime varovalo in ne
empirično potrjen prag sprejemanja.

Statični modelni adapter uporablja tudi omejene operativne opise motive enumov,
da enaka vidna semantika v slovenščini in angleščini ne dobi različnega ID-ja.
`attachment`, `body_alarm`, `boundary_alarm`, `broken_scene` in `motor_pattern`
so v tem adapterju razredi hipotez nad vidnim paketom, ne trditve o resnični
osebi ali empirično potrjena taksonomija. Eksplicitno protislovje v javnem
`uncertainty` polju pomeni protisloven odločilni signal tudi takrat, ko sta
posamezni opazki vsaka zase označeni kot `clear`.

Ta formula ne razreši vprašanja, kako AcceptanceState zanesljivo izmeriti, niti
ne dokazuje, da večja deklarirana vidnost ali fidelity pri resničnih osebah
povzroča boljšo interpretacijo. Pragovi, uteži in hash-selection politika
ostajajo zamenljivi pod OQ-ACCEPTANCE-001, OQ-ACCEPTANCE-002 in
OQ-TRANSLATION-001.

Vzročni pomen izbrane relacije `R_to_source`, visibility pragovi, formula med
acceptance in kakovostjo prevoda, semantična kalibracija ter zanesljivo merjenje
sprejemanja ostajajo odprti pod OQ-ACCEPTANCE-001,
OQ-ACCEPTANCE-002 in OQ-TRANSLATION-001. `overall_mode` ostane ekspliciten
input; B9 ga ne izpeljuje iz šestih relacij.

## OQ-BEHAVIOR-001 — začetna vedenjska tabela

Natančna deterministična tabela med acceptance mode, mandatom, Racijevo
interpretacijo, ConsciousDecision in BehaviorResultant še ni potrjena.
Ohraniti mora razhajanja in ne sme v enem `integrated_decision` stavku skriti
delay, oscillation, sabotage, blocked ali unresolved.

### B2 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, delno razrešeno samo na ravni sheme.
Mandatna in zavestna poravnava uporabljata `aligned`, `diverged`, `unknown` ali
`not_applicable`; tabela, ki iz teh stanj izpelje vedenje, ostaja za B10.

### B10 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, operativno razrešeno za začetni runtime,
teoretično in empirično še odprto. B10 zamrzne tri javne politike z revizijo
`1`: `b10-conscious-commit-table-v1`,
`b10-behavior-resolution-table-v1` in
`b10-racio-self-narrative-v1`.

Tabela ima strogo prioriteto. `unknown` acceptance ali mandat, ki ni
`actionable`, vedno vrne `deferred` zavestno odločitev in `unresolved`
vedenje. `Actionable` pomeni status `resolved`, `delegated` ali
`functionally_overridden` ter nenull `option_id`. Pri `accepting` Racio zavestno
sprejme mandat in vedenje ga izvede. Pri `mixed` se mandat sprejme in izvede,
če je R med strukturnimi viri ali če vsaj ena preverjena interpretacija
strukturnega vira E/I sklepa isti `option_id`; sicer Racio ob lastni možnosti
zavestno izbere svojo možnost in vedenje ostane `oscillating`, brez nje pa se
odločitev odloži in vedenje je `delayed`. Pri `conflicted` Racio ob lastni
možnosti zavestno izbere svojo možnost, vedenje pa je `sabotaged` tudi ob
naključnem ujemanju z mandatom; brez Racijeve možnosti sta odločitev in vedenje
`blocked`.

Tabela ne uporablja pragov relacij, keywordov, confidence, karakternih uteži,
B9 acceptance-fidelity audita, `TranslationGap` ali skritih nativnih motivov.
`AcceptanceState.overall_mode` ostaja ekspliciten vhod, governance in
authority tiers pa nespremenjeni. Natančen strojno berljiv zapis je v
`knowledge/canon_v2/acceptance.yaml` pod `initial_behavior_mapping`.

Odprto ostaja, ali ta začetna tabela psihološko ali empirično ustrezno modelira
vedenje, kako naj se kalibrira in kateri prihodnji dokaz upraviči njeno
zamenjavo. Prihodnja revizija zato potrebuje nov policy ID oziroma revizijo in
ne sme tiho spremeniti pravil `v1`.

## OQ-EGO-001 — kanonična in opisna polja Ega

Katera polja `EgoMeasure` in `EgoCompositionSnapshot` so nujna arhitekturna
jedra ter katera samo uporabne opisne projekcije? Source-supported je meja, da
Ego ni četrti razum; Measure/Trace/Snapshot so izvedbena operacionalizacija.

## OQ-EGO-002 — izračun kompozicijskega posnetka

Kako se iz append-only sledi reproducibilno izračunajo motivi, konflikti,
prevodne napake, razrešene in nerazrešene napetosti, commitmenti in trenutni
»odsek skladbe«? Vsaka izpeljava mora navesti `evidence_measure_ids`.

### B4 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, operativno razrešeno za deterministični
composition skeleton. Agregacija uporablja samo natančno ujemanje eksplicitnih
strukturiranih nizov, brez embeddingov, LLM reflektorja ali skritih uteži.
Ponavljajoči konflikt, prevodna napaka ali odnosni vzorec zahteva pojav v vsaj
dveh različnih measureih; strukturna identiteta, eksplicitna napetost,
`simulated_spoznanje` in zavestni commitment se lahko zapišejo že iz enega
measurea. `current_section` je število appendanih measureov, čas snapshota pa
čas zadnjega measurea. Vsako objavljeno polje ima ustrezen content-addressed
`SourcedEgoClaim` z natančnimi `evidence_measure_ids`. Popravek spremeni hash
sledi in zato identiteto nove izpeljave, nikoli pa ne prepiše ciljnega measurea.
Semantična podobnost in politika razrešenih napetosti ostajata odprti.

## OQ-PROJECTION-001 — projekcije zgodovine trem razumom

Kakšne so dokončne sheme in pravila posodobitve za RacioProjection,
EmocioProjection in InstinktProjection? Projekcija sme vplivati na naslednji
svet/spomin, ne pa izreči četrtega mnenja ali retroaktivno spreminjati tracea.

### B4 izvedbena odločitev — 2026-07-13

Status: `implementation_hypothesis`, operativno razrešeno za začetne projekcije.
Vse tri projekcije so deterministično in content-addressed izpeljane iz istega
`EgoTrace`, zahtevajo njegov hash ter za vsako objavljeno trditev navedejo
measure ID-je. Racio prejme kronologijo, opažena dejstva, izjave, commitmente in
vzročne povezave; Emocio strukturirane scene, vedenjske statusne vzorce in
želene transformacije; Instinkt body-state/rollout posledice ter alarmne
trditve. Prazna še neizpeljana polja ne vsebujejo nadomestnih domnev. Končne
sheme, semantično združevanje in update politika svetov ostajajo odprti.

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

## OQ-EVAL-001 — semantične metrike C2

Kako naj evaluator meri semantično pot, prevodno popačenje, kalibracijo,
ponavljajoče motive in dvojezično skladnost, ne da bi keyworde, modelnega
judgea ali skriti ground truth spremenil v bližnjico do rezultata?

### C2 izvedbena odločitev — 2026-07-14

Status: `implementation_hypothesis`, operativno razrešeno za deterministični
predmodelni evaluator C2. Konsolidirana politika je
`knowledge/canon_v2/evaluation.json`; njene dimenzije ostanejo ločene in se ne
združijo v en globalni »REI score«.

Kalibracija je v C2 merjena na ravni posameznega ročno pregledanega primera.
Gold cilj je `1`, kadar kandidat prestane vse semantične zahteve primera razen
same kalibracije, sicer `0`; Brierjeva napaka je
`(confidence - cilj) ** 2`. Začetni fixture prag je `0.25`. To je test
notranje skladnosti confidencea, ne empirični dokaz kalibriranosti modela ali
populacije. Pri abstinenci se pravilnost najprej določi glede na pričakovano
abstinenco primera.

Oznake `rationalization`, `minimization` in `projection` se nikoli ne sklepajo
iz keyworda ali samo iz neskladnega option ID-ja. Vsaka taka oznaka zahteva
ekspliciten evaluatorjev evidence zapis: vrsto dokaza, vidne podporne ID-je,
kandidatove strukturirane claim ID-je, morebitne kontradiktorne claim ID-je in
pričakovano oznako. `Rationalization` pomeni, da self-justification nadomesti
vidno nepodprto ali kontradiktorno razlago; `minimization` eksplicitno
zmanjšanje vidnega signala brez podpore; `projection` pa pripis lastnega stanja
ali motiva izvornemu razumu brez vidne podpore. Če tak dokaz ni dovolj popoln,
je oznaka `unknown`. Ground truth ostane samo v evaluatorju.

Za C2 recurring-motif metriko mora vsak ovrednoteni motiv citirati vsaj dva
različna measure ID-ja iz iste sekvence. Kandidatov motiv brez tega praga je
false positive; pričakovani motiv brez veljavnega kandidata je false negative.
To pravilo velja za evaluatorjeve recurring motif zapise in ne spreminja
obstoječe B4 možnosti, da se nekatera posamezna runtime polja zapišejo že iz
enega measurea.

Dvojezična avtomatska metrika primerja strukturiran semantični podpis:
`mind`, `option_id`, `abstains`, urejene `route_tags`, `evidence_ids` in
`interpretation_class`. Slovenščina ostane avtoritativna, angleščina pa
operativni gloss. Natančno ujemanje podpisa ne dokazuje kakovosti naravnega
prevoda; to ostane predmet slepega človeškega pregleda. C2 zato ne uporablja
embeddingov ali modelnega judgea za avtomatsko dvojezično gold odločitev.

## Izrecno zaprte smeri, ki niso odprta vprašanja B1

- QLoRA, LoRA, SFT, training dataset in izbor končnega modela niso v obsegu.
- Ego ni četrti agent ali odločevalec.
- Generirana slika ne ustvarja grounded evidence.
- Decimalne uteži, keyword sprejemanje in situacijski override niso dovoljena governance pravila.
- Psihološka diagnoza, karakteriziranje resničnih oseb in medicinske trditve niso cilj sistema.
