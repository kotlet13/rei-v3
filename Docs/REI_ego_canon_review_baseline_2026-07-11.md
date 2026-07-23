# REI Ego canon review — izhodišče 2026-07-11

Status: analitični izvleček za nadaljnjo razpravo. Dokument še ne določa
končne izvedbene specifikacije in nima runtime učinka.

## Namen

Ta zapis povzema ugotovitve pregleda primarnih REI dokumentov, Erosovih
komentarjev, trenutnega canona v2, legacy runtimea in načrta za nadaljnjo
implementacijo. Namen je ohraniti skupno izhodišče za natančnejšo definicijo
Ega.

## Osrednja ugotovitev

Ego v simulatorju ne sme biti četrti razum, samostojen LLM-agent ali nov vir
odločitev.

Začetni knjižni odlomek Ego opisuje kot doživeti »Jaz« oziroma zavest, ki živi
v svetu, sestavljenem iz treh procesorskih pogledov, vendar nima lastnih čutov
ali procesorske poti. Erosov poznejši komentar začetno prispodobo zoži in Ego
opredeli kot skupno rezultanto vseh treh miselnih procesov.

Obe perspektivi je mogoče uskladiti tako:

> Ego je izpeljano, enotno stanje doživljanega jaza in sveta, ki nastane iz
> Racia, Emocia in Instinkta. Je rezultat procesov, ne dodatni procesor.

## Ločnice, ki jih mora ohraniti arhitektura

1. `Ego != Racio`.
2. Ego ne ustvari lastnega `MindProposal`.
3. Ego nima neposrednega čutnega vhoda.
4. Racio je neposredno zavestno in besedno poročljiv vmesnik, ne celotna
   zavest ali objektivna resnica.
5. Emocio in Instinkt sta zavestno dostopna samo prek negotovega Racijevega
   prevoda.
6. Značaj je stabilna ordinalna razporeditev avtoritete med tremi razumi.
7. Trenutna aktivnost, razpoložljivost, delegacija in sprejemanje ne spremenijo
   značaja.
8. Odločitev, izvršeno vedenje, Racijeva razlaga in `spoznanje` niso ista stvar.
9. Soglasje vseh treh je notranja konvergenca, ne dokaz zunanje resničnosti.
10. Enako dejanje lahko nastane iz različnih procesorskih sklepov.

## Kaj v trenutnem načrtu že drži

- odstranitev LLM Ego Integratorja;
- deterministična ordinalna arbitraža;
- profilno slepi začetni predlogi za kontrolirane teste;
- ločitev strukturne avtoritete od delegacije in razpoložljivosti;
- označevanje besedila Emocia in Instinkta kot Racijevega prevoda;
- ločitev zavestne odločitve, napovedi vedenja in `spoznanja`;
- prepoved diagnoze, terapije, duhovne avtoritete in trditev o znanstveni
  dokazanosti.

## Glavne odprte vrzeli

### Ego je v `DecisionResultant` preveč skrčen

Odločitev je samo en dogodek znotraj širšega doživetega sveta. Potreben je
trajnejši izpeljani objekt, ki lahko vsebuje:

- trenutno doživeto sliko sveta;
- model samega sebe;
- modele drugih oseb;
- zavestno Racijevo poročilo;
- stanje odnosov med razumi;
- sprejeto odločitev;
- negotovost glede skritih izvorov;
- napoved vedenja;
- spremembo sveta po izkušnji.

Delovno ime je `EgoResultantV2` ali `EgoStateV2`. Ime ne pomeni agenta.

### Svet potrebuje zgodovino

Konkretnega odziva ne določa samo značaj, temveč vsebina predstav, spominov,
vrednot, ciljev, pričakovanj in modelov drugih ljudi, ki jih je oseba nakopičila.
Zamrznjeni procesorski predlogi so zato dober test arbitraže, niso pa popolna
simulacija osebe.

### Spoznanje potrebuje isti sklep, ne samo isto dejanje

`MindProposal` mora ločiti normalizirani sklep oziroma propozicijo od izbire
dejanja. Trije razumi lahko izberejo isto dejanje zaradi medsebojno
nezdružljivih sklepov; to še ni nujno `spoznanje`.

### Sprejemanje je relacija

Sprejemanje ne pomeni enake moči, enakega mnenja, sreče ali previdnega
vedenja. Pomeni medsebojno priznanje, toleranco, sodelovanje in možnost
omejene delegacije ob ohranjeni hierarhiji.

### Manjka možnost, da razum nima stališča

Razlikovati je treba med `position`, `abstain_no_view`, `unknown`,
`unavailable` in `delegated`. Vodilni razum brez stališča lahko prepusti
odločitev naslednjemu; nestrinjajočega vodilnega ni dovoljeno obiti, kot da je
odsoten.

## Epistemična meja

`direct_source` pomeni, da je trditev neposredno zapisana v REI viru. Ne
pomeni, da je empirično ali znanstveno potrjena. Projekt naj se predstavlja kot
REI-konceptualni simulator oziroma simulator po teoriji REI, dokler ne obstaja
neodvisna empirična validacija.

Medicinske, metafizične, zgodovinske, prehranske, spolne in družbeno
posplošujoče trditve širšega gradiva ne sodijo v aktivni procesorski canon ali
trening.

## Začetna izvedbena hipoteza

Najbolj obetavna začetna razmejitev je:

```text
EgoResultantV2
  = deterministična projekcija(
      tri procesorske presoje,
      značajska avtoriteta,
      odnosi sprejemanja,
      razpoložljivost in delegacija,
      osebni svet in zgodovina
    )
```

Ta hipoteza še ne določa, katera polja so kanonična, kako se izračuna enotna
perspektiva in kateri deli smejo biti samo opisni. To je naslednje vprašanje za
razpravo.

## Glavni pregledani viri

- `Docs/del1odsekN.pdf`, PDF strani 3–5;
- `Docs/del2odsekN.pdf`, PDF strani 1–7;
- `Docs/Racio.pdf`, `Docs/Emocio.pdf`, `Docs/Instinkt.pdf`;
- `Docs/REI osnove.docx` in `Docs/erosov značaj.docx`;
- `Docs/Eros - pogovori.pdf`, posebej strani 23, 38–39, 51–53, 76–78,
  88–89, 99, 104, 124, 165–166 in 183–186;
- `knowledge/canon/claims_v2.jsonl`;
- `knowledge/canon/processors_v2.yaml`;
- `knowledge/canon/character_rules_v2.yaml`;
- `plans/REI_v3_Codex_canonical_v2_QLoRA_plan_2026-07-10.md`.
