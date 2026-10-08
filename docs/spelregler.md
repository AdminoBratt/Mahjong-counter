# Spelregler & poänglogik

Backend ansvarar för ALL matematik. Frontend skickar bara rådata.

## Brickor
- **Serier**: Tecken 1-9, Bambu 1-9, Cirkel 1-9
- **Vindar**: Öst, Syd, Väst, Nord
- **Drakar**: Röd, Grön, Vit
- **Blommor**: 1,2,3,4 (Öst=1, Syd=2, Väst=3, Nord=4)
- **Årstider**: 1,2,3,4 (Öst=1, Syd=2, Väst=3, Nord=4)

## Vindrotation
- Rond 1: spelare väljer startvind manuellt.
- Efter varje rond roterar vindarna **moturs** (Öst→Nord→Väst→Syd→Öst).
- **Undantag**: om Öst-spelaren gör Mahjong stannar vindarna (ingen rotation).
- Oavgjort (muren tar slut): ingen rotation, ingen poäng.
- Rondens vind (prevailing wind) roterar inte ännu, se "Känd teknisk skuld" i CLAUDE.md.

## Baspoäng

### Kombinationer
| Kombination | Poäng |
|---|---|
| 3-följd (Tjao) | 0p |
| 3tal (Pong) 2-8, på bordet | 2p |
| 3tal 1,9,vind,drake, på bordet | 4p |
| 3tal 2-8, på hand | 4p |
| 3tal 1,9,vind,drake, på hand | 8p |
| 4tal (Kong) 2-8, på bordet | 8p |
| 4tal 1,9,vind,drake, på bordet | 16p |
| 4tal 2-8, på hand | 16p |
| 4tal 1,9,vind,drake, på hand | 32p |
| Par i drake, rondens vind eller egen vind | 2p |
| Blomma eller årstid | 4p per st |

### Mahjong-bonusar (endast vinnaren)
| Bonus | Poäng |
|---|---|
| Gjort Mahjong | 20p |
| Vinnande bricka från muren | 2p |
| Vinnande bricka är enda möjliga | 2p |
| Vinnande bricka är lös bricka* | 10p |
| Vinnande bricka är sprängt 4tal** | 10p |
| Hand med bara följder | 10p |

*Lös bricka = extra bricka från andra sidan muren efter blomma/årstid/kong.
**Sprängt 4tal = annan spelare försöker komplettera Kong, du gör Mahjong på den brickan.

## Dubblingar
Stackas multiplikativt: Xp × 2^n

### Allmänna dubblingar (alla spelare)
| Situation | Dubblingar |
|---|---|
| 3tal/4tal i drake, rondens vind eller egen vind | 1× per st |
| Egen blomma eller årstid (rätt nummer för din vind) | 1× per st |
| Alla 4 blommor | 3× |
| Alla 4 årstider | 3× |
| Alla 8 blommor + årstider | 6× |

### Mahjong-dubblingar (endast vinnaren)
| Situation | Dubblingar |
|---|---|
| Vinner genom dragning från muren | 1× |
| Hand utan någon följd | 1× |
| Hand består enbart av 1or, 9or, drakar och/eller vindar | 1× |
| Hela handen (exkl. par) från en och samma serie | 3× |
| 3tal/4tal av två drakar + par av den tredje | 3× |

## Betalningslogik

**Vinnaren** får betalt av alla tre förlorare:
- Varje förlorare betalar vinnarens finalpoäng.
- Om Öst är inblandad (som vinnare ELLER förlorare) fördubblas beloppet.

**Förlorarna** gör upp sinsemellan (vinnaren betalar ingenting):
- Den med högre poäng får skillnaden från den med lägre poäng.
- Alla betalningar till/från Öst fördubblas.

**Exempel**: Nordan vinner (48p), Öst (24p), Syd (8p), Väst (32p)
- Nordan får: 48 (Syd) + 48 (Väst) + 96 (Öst×2) = +192p
- Väst får: (32-8) från Syd = +24p, (32-24)×2 från Öst = +16p
- Öst får: (24-8)×2 från Syd = +32p
- Syd betalar alla, får inget

**Oavgjort**: ingen poäng, ingen betalning, vindarna roterar inte.

## Poänginmatning, UI-flöde (3 vyer per spelare per rond)

### Vy 1 — Baspoäng
- Antal 3-följder (automatiskt 0p, bara för info)
- Lista med 3tal/4tal: för varje, (bord/hand) × (vanlig 2-8 / special 1,9,vind,drake)
- Par i drake / rondens vind / egen vind (2p)
- Antal blommor (markera vilka nummer)
- Antal årstider (markera vilka nummer)
- Gjorde jag Mahjong? (ja/nej, öppnar extra fält)
  - Om ja: checkboxar för varje Mahjong-bonus

### Vy 2 — Allmänna dubblingar (alla spelare)
Användaren anger drak- och vind-3tal. Blommor och årstider visas utifrån Vy 1 (se Beslut 28):
- 3tal/4tal i drake (vilken?)
- 3tal/4tal i rondens vind
- 3tal/4tal i egen vind
- Egen blomma/årstid
- Alla blommor / alla årstider / alla 8

### Vy 3 — Mahjong-dubblingar (endast vinnaren)
- Vann genom dragning
- Ingen följd i handen
- Enbart 1or/9or/drakar/vindar
- Enbart en serie
- Två drakar + par av tredje

## Beslut
1. Från muren: en kryssruta ger både bonusen 2p och dubblingen 1×.
2. Lös bricka räknas också som dragning från muren (10p + 2p + 1×). Sprängt 4tal kan inte kombineras med från muren eller lös bricka.
3. Ett par som är både rondens vind och egen vind ger 2p. Ett 3tal/4tal som är både rondens vind och egen vind ger 2×.
4. Alla 8 blommor + årstider är summan av alla 4 blommor och alla 4 årstider, alltså 6×, inte 12×.
5. Egen blomma/årstid stackas med alla 4 blommor/årstider.
6. "Bara följder" och "ingen följd" härleds från antalet följder och 3tal/4tal. Bonusen för bara följder kräver att paret inte är poänggivande.
7. Två drakar + par av tredje ger 3× utöver 1× per drak-3tal, alltså 5×. Paret måste vara markerat som poänggivande.
8. "Enbart 1or/9or/drakar/vindar" och "ingen följd" gäller båda (2×).
9. Inget poängtak och ingen avrundning.
10. Vinnaren måste ha exakt fyra grupper (följder + 3tal/4tal), övriga högst fyra.
11. En förlorare med fler poäng än vinnaren betalar ändå vinnarens poäng fullt ut och får inget av vinnaren.
12. Två förlorare med lika poäng betalar ingenting till varandra, även om den ena är Öst.
13. Vid oavgjort ignoreras poängen helt, men alla fyra spelare måste ändå finnas med.
14. Vinnarens poäng påverkar inte förlorarnas uppgörelse sinsemellan, eftersom vinnaren inte deltar där.
15. Öst-spelaren anges med spelar-id till betalningslogiken, inte genom allas vindar.
16. Betalningslogiken (`settle`) ligger i `backend/app/scoring.py`, ingen egen modul.
17. Vindrotationen flyttar varje spelares vind ett steg Öst→Nord→Väst→Syd→Öst, så Syd-spelaren blir ny Öst.
18. Vindrotationslogiken (`rotate_winds`) ligger i `backend/app/scoring.py`, ingen egen modul.
19. `rotate_winds` tar spelar-id → vind och vinnarens spelar-id, `winner=None` betyder oavgjort (samma form som `settle`).
20. `rotate_winds` returnerar bara nästa ronds vindar. Rondnummer hör till 3.4 och rondens vind till den tekniska skulden.
21. Oavgjort anges uttryckligen av varje spelare (fältet `draw` i `submit_score`) och härleds aldrig.
22. Mahjong anges i `score_input.mahjong`. Det finns inget separat `mark_mahjong`.
23. Oavgjort och Mahjong i samma inlämning nekas (`invalid_score`).
24. En spelare får skicka in igen tills ronden är avslutad. Den senaste inlämningen gäller.
25. Ronden avslutas när alla fyra har lämnat in och antingen exakt en har Mahjong och ingen valt oavgjort, eller alla fyra valt oavgjort.
26. Alla andra kombinationer avslutar inte ronden. Läget visas som en konflikt (`no_mahjong`, `multiple_mahjong`, `draw_disagreement`) och löses genom att någon skickar in igen.
27. En avslutad rond kan inte ångras eller ändras (se "Känd teknisk skuld" i CLAUDE.md).
28. Vy 2 föreslår inga drak- eller vind-3tal, eftersom Vy 1 bara anger om ett 3tal är 1, 9, vind, drake och inte vilken bricka. Antalet sådana 3tal är taket för drak- och vind-3tal tillsammans (0 = fälten avstängda). Är egen vind också rondens vind finns en kryssruta som sätter både `round_wind_sets` och `own_wind_sets`. Egen blomma/årstid och alla 4/alla 8 visas skrivskyddat som ja/nej och ändras i Vy 1. Inga multiplikatorer visas förrän backend räknat dem.
29. "Hela handen från en serie" kan inte kombineras med drak- eller vind-3tal. Kontrollen täcker bara de drak- och vind-3tal som angetts i Vy 2. Ett 3tal i 1, 9, vind, drake som inte angetts där går inte att skilja från 1or/9or i serien.
30. "Hela handen från en serie" och "Enbart 1or/9or/drakar/vindar" utesluter varandra. En serie har bara två ytterbrickor, så fyra grupper kan inte alla vara 1or/9or i samma serie.
31. I Vy 3 är en ruta som inte är tillåten avstängd och har en synlig förklaring under sig, även när det är den andra rutan som spärrar den. En ruta som redan är ikryssad men inte längre tillåten (till exempel efter en ändring i Vy 1 eller Vy 2) förblir klickbar så att den kan kryssas ur. Felet visas under rutan och Nästa är spärrat tills det är rättat.
32. Klienten räknar inga poäng. Uträkningen av en inlämning (`base_points`, `doublings`, `final_points`) kommer från servern i `submissions` och visas som den är. Före inskick visas bara valen i klartext.
33. "Skicka in" är avstängd och visar "Skickar…" tills servern svarat, antingen med inlämningen i `lobby_update` eller med ett fel. Ingen extra bekräftelsedialog: bekräftelseskärmen är bekräftelsen och inlämningen kan ändras tills ronden är avslutad.
34. Efter inskick visas väntläget med den egna uträkningen och vilka som lämnat in. Andras poäng och val visas inte förrän ronden är avslutad.
35. "Ändra min inmatning" börjar i Vy 1, ifylld från serverns version. Den förra inlämningen gäller tills en ny skickas. Avslutas ronden under tiden visas "Rond N avslutades medan du ändrade. Din förra inlämning gällde."
36. Vid en konflikt visas en förklaring och knappen "Ändra min inmatning". Bara där visas vilka som angett Mahjong eller Oavgjort.
37. Poäng och totaler visas med tecken (+/−). Noll visas utan tecken.
38. Spelvyns huvud visar ställningen: varje spelares namn, vind och total, direkt från `players` i `lobby_update`.
39. Nästa rond startas med en knapp "Nästa rond" hos varje spelare, inte automatiskt (3.8b).
40. Klienten läser rondresultatet bara från `last_round` i `lobby_update`, både live och efter omladdning. `round_complete` skickas kvar men används inte av klienten.
41. Resultatvyn visar vem som vann (eller oavgjort), rondens vind och en tabell i sätesordning: spelare, vind i ronden, baspoäng, dubblingar (antal), slutpoäng, betalning, ny total och nästa vind. Den egna raden märks "(du)", vinnaren "Mahjong". Betalning och ny total visas stort med tecken (Beslut 37).
42. Vid oavgjort visas baspoäng, dubblingar och slutpoäng som "–" och betalningen som 0 (Beslut 13).
43. Under tabellen står alltid: "Betalningar till och från Öst dubblas. Förlorarna gör upp sinsemellan. Summan av alla betalningar är 0."
44. Resultatet visas tills spelaren klickar "Nästa rond" eller har lämnat in i nästa rond. Valet sparas inte: en omladdning före inlämning visar resultatet igen, en omladdning efter inlämning visar väntläget.
