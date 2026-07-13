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

## OQ-RANGE-001 — območja confidence in intensity

`BodyState` je predlagan v območju `[0, 1]`, za druga polja confidence,
intensity, fidelity in valuation pa plan ne določa popolne semantike,
kalibracije ali obravnave manjkajoče vrednosti. Ne predpostavljaj, da
confidence pomeni značajsko avtoriteto.

## OQ-NATIVE-001 — dokaz neodvisne procesorske poti

Kateri kratek, opazljiv dokaz pokaže, da so R, E in I do sklepa prišli po
lastnih poteh, ne da bi sistem zahteval ali razkrival dolgo skrito verigo
razmišljanja? Kandidati so provenance evidence ID-jev, nativni artefakti,
route tags in kratek decision bridge.

## OQ-RACIO-001 — RacioInputPacket

Plan opisuje Racijev vhod semantično, ne pa z dokončno shemo. B2 mora določiti
minimalna polja, pri čemer profil, rang in skriti E/I motivi v kontroliranem
načinu ostanejo prepovedani.

## OQ-TRANSLATION-001 — zvestoba Racijevega prevoda

Kako evaluator loči uporaben prevod od opustitve, racionalizacije,
minimizacije, projekcije ali napačne klasifikacije? `TranslationGap` ne sme
postati ground-truth namig Raciju in ne sme zahtevati razkritja chain-of-thought.

## OQ-EMOCIO-001 — vizualna valuation in renderer

Katere valuation dimenzije so dovolj stabilne za prvi Emocio PoC in kako se
kalibrirajo? Kdaj je renderer samo vizualizacija in kdaj legitimni del
manifestacije? Končni model/provider ni izbran. Pred kakršnimkoli generiranjem
slik je potrebna uporabnikova izrecna potrditev.

## OQ-INSTINKT-001 — virtual-body dinamika

Katera minimalna deterministična dinamika zadostuje za nevarnost, izgubo,
meje, zaupanje, navezanost, pomanjkanje in okrevanje, ne da bi predstavljala
medicinski ali fiziološki model? Vsa sprejeta pravila morajo ostati vidna v
`instinkt.yaml` in označena po statusu.

## OQ-PAIR-001 — spor dveh enakovrednih vodilnih razumov

Pregledani viri ne dajejo univerzalnega pravila za vsak spor vodilnega para.
Začetna runtime politika `unresolved` in omejeni informacijski pogajalski krog
sta izvedbeni hipotezi; podrejeni razum, Racio, confidence ali LLM niso
samodejni tie-breakerji.

## OQ-DELEGATION-001 — delegacija, nadomeščanje in odsotnost stališča

Kateri minimalni podatki ločijo prostovoljno delegacijo, začasno operativno
nadomeščanje, funkcionalno omejitev, `abstain_no_view`, `unknown`,
`unavailable` in močan signal podrejenega razuma? Nobena kategorija sama po
sebi ne spremeni strukturnega karakterja.

## OQ-AVAILABILITY-001 — prag funkcionalnega overridea

Kdo ali kaj lahko razglasi funkcionalno nedostopnost, pri katerem pragu in s
kakšnim dokazom? `override_reason` mora biti ekspliciten; stres, strah, mood,
keyword ali confidence niso zadosten razlog.

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

## OQ-LIFE-001 — metafizična meja Življenja

Odnos med Egom in pojmom Življenja ostaja ločeno raziskovalno področje.
Trenutni sistem nima operativne definicije njegove avtoritete, zato ne
implementira `LifeAgent`, `LifeDecision` ali `LifePrompt`.

## OQ-SAFETY-001 — javni safety caveat

Kakšna bo dokončna shema, lokalizacija in propagacija javnega opozorila, da je
izdelek konceptualni simulator po teoriji REI, ne diagnoza, empirično potrjena
psihologija ali karakterizacija resnične osebe?

## OQ-NAMING-001 — pogodbeno poimenovanje

Pred B2 je treba poenotiti `VisualSituationPacket`/`EmocioInputPacket` in
`InstinctAssociation`/`InstinktAssociation`. Za testni slikovni adapter je B1
sprejel ime `NullImageRenderer`. Slovenski izraz Instinkt ostane kanoničen,
angleški JSON ključi pa so lahko operativni.

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
