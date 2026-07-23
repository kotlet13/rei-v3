# REI canonical v2 - odprta vprašanja

Status: `open_questions`
Canon language: Slovenian
Operational gloss language: English
Runtime effect in Phase 1: none

Ta dokument evidentira mesta, kjer pregledani viri še ne zadoščajo za trdo
izvedbeno pravilo. Odprto vprašanje ni dovoljenje, da ga model ali evaluator
zapolni s površinsko hevristiko.

Registry uporablja tri vrste izvora:

- `OD` - osnovni dokument projekta;
- `EK` - Erosov komentar v dokumentu `Eros - pogovori.pdf`;
- `IZ` - projektna oziroma implementacijska izpeljava, ki ni neposredna
  psihološka trditev primarnega vira.

## 1. Spor dveh enakovrednih vodilnih razumov

Viri podpirajo obstoj dveh enakovrednih vodilnih razumov in opisujejo težje
odločanje, ne določajo pa univerzalnega razreševalnega pravila za vsak njun
spor. Do dodatnega vira ostane tak spor eksplicitno nerešen; podrejeni razum
ne postane samodejni razsodnik.

- Registry: `C-PAIR-001`
- Potreben dokaz: neposreden OD odlomek ali jasno omejen EK primer, ki loči
  splošno pravilo od posameznega primera.
- Poznejša izvedba: Faza 3, ne Faza 1.

## 2. Meja med delegacijo in funkcionalnim nadomeščanjem

Vir na strani 23 podpira prepuščanje nalog pri sprejemanju, strani 104 in 145
pa začasno večjo izvedbeno vlogo ob manjši razpoložljivosti vodilnega razuma.
Odprto ostaja, kateri minimalni podatki zadoščajo, da sistem razlikuje:

- prostovoljno delegacijo;
- začasno operativno nadomeščanje;
- funkcionalno omejitev;
- navaden močan signal podrejenega razuma.

Nobena od teh možnosti sama po sebi ne sme spremeniti značaja.

## 3. Operativni dokaz neodvisne poti pri spoznanju

Kanon zahteva isti sklep vseh treh razumov. Pred deterministično izvedbo je
treba določiti, kateri kratek, opazljiv dokaz pokaže, da so trije razumi do
sklepa prišli po lastnih poteh, brez učenja ali razkrivanja dolge skrite verige
razmišljanja.

- Registry: `C-SPOZ-001`
- Kandidati za poznejši eval: source evidence IDs, kanonične route tags in
  kratek decision bridge.

## 4. Merjenje sprejemanja

Viri sprejemanje povezujejo s sodelovanjem, toleranco in prepuščanjem nalog.
Odprto ostaja, kako ga zanesljivo oceniti iz omejenega opisa osebe. V
kontroliranih evalih mora biti zato stanje sprejemanja ekspliciten vhod, dokler
ločen pregledan dataset ne podpre classifierja.

## 5. Pomen izraza kulisa

Izraz je rezerviran, vendar potrebuje širši source sweep, preden dobi ozko
strojno klasifikacijo. Za zdaj glossary uporablja konservativno definicijo
priučene predstave ali vedenjskega vzorca, ki lahko prikrije neskladje med
razumi. Izraz se ne sme uporabljati kot splošna oznaka za vsako navado.

## 6. Konvencija strani in dokumentnih lokatorjev

PDF viri uporabljajo fizično številko strani. Kratki OD dokumenti uporabljajo
stran najnovejšega renderja in opis odstavka v `source_locator`. Markdown
izvedbene specifikacije nimajo stabilne strani, zato uporabljajo `page: null`
in obvezen naslov razdelka. Ob spremembi preloma strani je treba ponovno
preveriti vse OD lokatorje.

## 7. Meja varnega jedra

Medicinske, metafizične, zgodovinske in družbeno posplošujoče trditve iz
širšega gradiva niso del začetnega procesorskega kanona. Če jih bo projekt
pozneje raziskoval, potrebujejo ločen registry, risk review in privzeto
izključitev iz treninga.

## 8. Migracija legacy uteži

Kanon v2 zapisuje ordinalno avtoriteto. Način združljivostnega prikaza starih
decimalnih uteži in migracija poročil sta nalogi poznejše faze. Ta dokument ne
določa preslikave, ki bi uteži ponovno uvedla v odločanje.

## 9. Zvestoba Racijevega prevoda

Viri pravijo, da zavestni dostop do Emocia in Instinkta poteka prek Racia in
da pri tem pride do prilagajanja. Odprto ostaja, kako v evalih ločiti uporaben
operativni prevod od Racijevega popačenja ali racionalizacije. Oznaka
`translated_by_racio` zato ne pomeni, da je prevod dobeseden ali popolnoma
zvest hipotetičnemu nezavednemu signalu.
