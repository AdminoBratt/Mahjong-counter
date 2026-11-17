# Mahjong Score Tracker

Webbapp för realtids-poängräkning i Mahjong. Fyra spelare går in från sina
datorer (webbläsare), skapar/går med i en lobby via en 6-teckens kod och matar
in sina poäng rond för rond. All matematik sker i backend. Realtid via WebSockets.

## Stack
- Frontend: React + TypeScript (Vite), desktop-first för pc-webbläsare (`frontend/`)
- Backend: Python FastAPI + WebSockets (`backend/`)
- Lagring: INGEN databas. Allt spelstate hålls i minnet i backend (se "Lagring i minnet").
- Auth: gästinlogg via smeknamn, ingen e-post eller lösenord
- Deployment: en enda Docker-tjänst på Railway (`Dockerfile` i roten). FastAPI serverar API:et under `/api`,
  WebSocket på `/ws` och den byggda frontenden (fallback till `index.html`). Ingen Vercel, ingen databas.
  Varje merge till `main` startar om tjänsten och raderar pågående spel.

## Projektstruktur
```
Wizardworks/
  frontend/          # React + TypeScript (Vite)
  backend/           # FastAPI
  docs/              # referensdokument (se nedan)
  Dockerfile         # bygger frontend + backend till en image (Railway)
  CLAUDE.md
```

## Så jobbar vi
1. Ta ETT steg i taget från `docs/faser.md`, i ordning. Gör aldrig flera steg på en gång.
2. Skriv en kort plan (vilka filer påverkas, vad ska göras) och vänta på mitt OK innan du skriver kod.
3. Implementera och skriv/kör tester för det nya.
4. Granska din egen diff (`git diff`) för korrekthet, säkerhet och buggar.
   Kör sedan `ponytail-review` för att hitta onödig komplexitet.
5. Jobba på en `feature/<kort-namn>`-branch. Conventional commits:
   `feat:` ny funktionalitet, `fix:` buggfix, `chore:` config/beroenden,
   `refactor:` omstrukturering utan ny funktionalitet.
6. Pusha och skapa PR med `gh pr create`.
7. Bocka av steget i `docs/faser.md` när det är klart och verifierat.

Om spelreglerna är oklara: fråga mig, gissa inte.

## Lagring i minnet
- Alla spel ligger i en `GameStore` i backend-processen (t.ex. en dict `{lobby_code: Game}`). Ingen databas, inga migrationer.
- Allt försvinner när backend startar om (deploy, krasch). Det är medvetet och accepterat.
- Kör bara EN backend-instans, annars hamnar spelare i olika minnen.
- Spelare ska kunna återansluta efter sidladdning med lobbykod + smeknamn.
- Städa bort inaktiva spel efter några timmar så att minnet inte växer.
- Ingen historik eller statistik sparas mellan spel. Poänghistoriken inom ett pågående spel lagras inte
  separat utan härleds ur rondresultaten.
- Håll lagringen bakom ett litet gränssnitt (`GameStore`) så att den kan bytas ut senare om det behövs.

## Viktiga regler
- All poängmatematik sker ENBART i backend. Frontend skickar antingen rådata (Vy 1–3) eller en slutpoäng som
  spelaren räknat själv, och räknar aldrig något. Betalningar, totaler och vindrotation räknas alltid i backend.
- WebSocket-events broadcastas alltid till ALLA spelare i lobbyn.
- API-rutter ligger under `/api` så att de inte krockar med frontendens sidor. `/ws` kontrollerar `Origin`.
- Desktop (pc-webbläsare) är primärt. Mobilanpassning prioriteras inte, men undvik att göra layouten omöjlig att använda på smal skärm.
- Poänglogiken (poäng, dubblingar, betalningar, vindrotation) ska ha enhetstester. Den är lätt att få fel.
- Inga e-postadresser samlas in.
- Hemligheter ska aldrig committas. Använd `.env`.
- UI-steg: kör ui-ux-pro-max först, andra designskills får komplettera men aldrig ersätta den.
  Följ designvalen under "Design" här i filen. Välj inga nya paletter eller typsnitt på egen hand.
- Skriv bara den kod ett steg kräver (ponytail). Poängmatematiken i backend ska ändå ha tester.

## Användbara kommandon
- Backend (från `backend/`): `uvicorn app.main:app --reload`
- Backend-tester (från `backend/`): `pytest`
- Frontend (från `frontend/`): `npm run dev`
- Frontend-tester för rena funktioner (från `frontend/`): `npm test` (Vitest, ingen DOM)
- Produktionsimage lokalt (från roten): `docker build -t mahjong-tracker .` och
  `docker run -e PORT=8080 -p 8080:8080 mahjong-tracker`, sedan http://localhost:8080

## Miljövariabler (backend)
```
CORS_ORIGINS=http://localhost:5173
```
Behövs bara lokalt (Vite på :5173 är en annan origin). I produktion är sida, API och `/ws` samma
origin, så inga variabler behövs. `PORT` sätts av Railway.

Valfria, standardvärdena räcker (städning av spel, se docs/events.md):
```
CLEANUP_INTERVAL_SECONDS=60     # hur ofta städningen körs
FINISHED_GAME_TTL_MINUTES=30    # avslutat spel, räknat från end_game
WAITING_GAME_TTL_MINUTES=30     # väntande spel utan anslutna spelare
IDLE_GAME_TTL_MINUTES=180       # pågående spel utan anslutna spelare
MAX_IDLE_HOURS=24               # alla spel utan aktivitet, även med anslutna spelare
```

## Referens (läs vid behov, inte hela tiden)
- Faser och status: `docs/faser.md`
- Spelregler, poäng, dubblingar, betalningar, UI-flöde: `docs/spelregler.md`
- Datamodell (modeller i minnet): `docs/datamodell.md`
- WebSocket-events: `docs/events.md`

Läs `docs/spelregler.md` innan du rör poängberäkning, betalningar eller vindrotation.
Läs `docs/datamodell.md` innan du rör spelmodellerna eller `GameStore`.

## Design
Följ alltid dessa val i alla UI-steg.
- Stil: glasmorfism, mörkt. Bläckblått, havreelfenben och 10% bärnstensorange. Ett enda mörkt tema, inget ljust läge.
  Glasytor (`.card`, ställningen, dialogen): genomskinligt elfenben + `backdrop-filter`, hårfin kant, svag överkantsglans,
  solid `#1d3148` som fallback. Spelbordsytor (`--felt`) är ett djupare, mörkare glas inuti. Bakom allt mjuka
  ljusfläckar i bodyns bakgrund (bara CSS-gradienter), annars finns inget att sudda.
- Typsnitt: Geist för UI-text, Geist Mono för poäng, lobbykod och betalningar. Självhostade via `@fontsource-variable`.
  Brödtext 16px / 1.5. `tabular-nums` globalt. Tusentalsavgränsare enligt `sv-SE`.
- Färger (kontrast mot `--bg` / glas ≈ `#283746` / `--felt` ≈ `#1b2734`, verifierat med skript):
  - `--bg #152638` (bläckblått), `--surface` elfenben 7%, `--felt` bläck 40%
  - `--text #e9e5d8` (havreelfenben) 12.2 / 9.7 / 12.0, `--text-muted #a5a8a5` 6.4 / 5.1 / 6.3
  - `--positive #7fd1a3` 8.5 / 6.7 / 8.3, `--negative #ff8f80` 7.0 / 5.5 / 6.9
  - `--accent #f18d46` (bärnstensorange, enda accenten, ca 10% av ytan: primärknappar, länkar, fokusring, "min" markering) 6.3 / 5.0 / 6.2
  - `--on-accent #152638` (text på accentknappar) 6.3
  - `--border` elfenben 14% (dekorativa linjer), `--border-input #7f8688` (fältramar) 4.2 / 3.3 / 4.1
- Poäng visas alltid med tecken (+/−), inte bara med färg.
- Form: 14px hörnradie överallt. Kontroller minst 44px höga. Fokus: 2px ring i `--accent`, offset 2px, tas aldrig bort.
- Etiketter ovanför fält, fel under fältet, aldrig placeholder som etikett.
- Rörelse: hover/tryck (150–200ms, knappar lyfts 1px och trycks ner), startvyn glider in en gång vid laddning.
  Avstängt vid `prefers-reduced-motion`. Inga animationsbibliotek, ingen Tailwind.
- Ikoner: inte valt ännu, välj när första ikonen behövs.
- Färger och typsnitt definieras som CSS-variabler i `frontend/src/styles/theme.css`.
  Hårdkoda aldrig färger eller typsnitt i komponenter, använd variablerna.

## Känd teknisk skuld
Medvetet uppskjutet, inte buggar.

- Prevailing wind (`Round.round_wind`) roterar inte ännu och är tills vidare fast `east`.
  Spelarnas individuella vindar roterar korrekt moturs. I riktig Mahjong byter rondens vind efter ett helt varv.
  Påverkar semantiken för dubblingen "3tal/4tal i rondens vind". Ingen felräkning nu eftersom
  `set_in_round_wind` är användarbekräftad indata i Vy 2. Uppskjuten till efter Fas 3.
- Ingen ångra: en avslutad rond kan inte ändras eller ångras. Felinmatning upptäckt efter att den fjärde
  spelaren lämnat in går inte att rätta i appen.
- Ingen "Ångra senaste ronden": med direkt slutpoäng avslutas ronden när den fjärde spelaren skickar. Har den
  som skickar sist skrivit fel (t.ex. en extra nolla) kan felet inte rättas, eftersom ronden redan är avslutad.
  Riskerna minskas av att talet visas stort före inskick och av kontrollen för jämna tal.
- Bara skaparen (plats 1) kan avsluta spelet. Kommer skaparen aldrig tillbaka går spelet inte att avsluta,
  utan det står kvar tills städningen tar bort det (3 h utan anslutna spelare, annars 24 h utan aktivitet).
- Ett pågående spel med en öppen flik tas bort först efter 24 h utan aktivitet (`MAX_IDLE_HOURS`). En lång paus
  mellan ronder längre än så avbryter spelet.
- En rond väntar på alla fyra, utan timeout. Kommer en frånkopplad spelare aldrig tillbaka står ronden still.

## Lärdomar
Fylls på löpande. När Claude gör ett fel: skriv in rättelsen här som en kort regel.

- Döda aldrig processer via namn (taskkill /IM, pkill) eftersom det kan stänga användarens egna program. Stäng bara processer du själv startat, via PID eller port, och kontrollera först att processen är din.
