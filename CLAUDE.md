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
- Ingen historik eller statistik sparas.
- Håll lagringen bakom ett litet gränssnitt (`GameStore`) så att den kan bytas ut senare om det behövs.

## Viktiga regler
- All poängmatematik sker ENBART i backend. Frontend skickar rådata (vad spelaren valt), backend beräknar allt.
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
- Produktionsimage lokalt (från roten): `docker build -t mahjong-tracker .` och
  `docker run -e PORT=8080 -p 8080:8080 mahjong-tracker`, sedan http://localhost:8080

## Miljövariabler (backend)
```
CORS_ORIGINS=http://localhost:5173
```
Behövs bara lokalt (Vite på :5173 är en annan origin). I produktion är sida, API och `/ws` samma
origin, så inga variabler behövs. `PORT` sätts av Railway.

## Referens (läs vid behov, inte hela tiden)
- Faser och status: `docs/faser.md`
- Spelregler, poäng, dubblingar, betalningar, UI-flöde: `docs/spelregler.md`
- Datamodell (modeller i minnet): `docs/datamodell.md`
- WebSocket-events: `docs/events.md`

Läs `docs/spelregler.md` innan du rör poängberäkning, betalningar eller vindrotation.
Läs `docs/datamodell.md` innan du rör spelmodellerna eller `GameStore`.

## Design
Följ alltid dessa val i alla UI-steg.
- Stil: Minimalism/Swiss + financial-dashboard-mönster, tema "jadefilt + röd drake". Ett enda mörkt tema, inget ljust läge.
- Typsnitt: Geist för UI-text, Geist Mono för poäng, lobbykod och betalningar. Självhostade via `@fontsource-variable`.
  Brödtext 16px / 1.5. `tabular-nums` globalt. Tusentalsavgränsare enligt `sv-SE`.
- Färger (kontrast mot `--bg` / `--surface` / `--felt`, verifierat med skript):
  - `--bg #0e1512`, `--surface #16201b`, `--felt #173a2c` (poängtavla, spelbordsytor)
  - `--text #e8eee9` 15.7 / 14.2 / 10.6, `--text-muted #9aaaa1` 7.6 / 6.9 / 5.2
  - `--positive #5cb88a` 7.7 / 6.9 / 5.2, `--negative #f07a6a` 6.8 / 6.1 / 4.6
  - `--accent #e0594a` (enda accenten: primärknappar, länkar, fokusring) 5.0 / 4.5 / 3.4. Text i accent aldrig på `--felt`.
  - `--on-accent #0e1512` (text på accentknappar) 5.0
  - `--border #2b3a32` (dekorativa linjer), `--border-input #66796f` (fältramar) 4.0 / 3.6
- Poäng visas alltid med tecken (+/−), inte bara med färg.
- Form: 8px hörnradie överallt. Kontroller minst 44px höga. Fokus: 2px ring i `--accent`, offset 2px, tas aldrig bort.
- Etiketter ovanför fält, fel under fältet, aldrig placeholder som etikett.
- Rörelse: bara hover/tryck (150–200ms). Avstängt vid `prefers-reduced-motion`. Inga animationsbibliotek, ingen Tailwind.
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
- En rond väntar på alla fyra, utan timeout. Kommer en frånkopplad spelare aldrig tillbaka står ronden still.

## Lärdomar
Fylls på löpande. När Claude gör ett fel: skriv in rättelsen här som en kort regel.

- Döda aldrig processer via namn (taskkill /IM, pkill) eftersom det kan stänga användarens egna program. Stäng bara processer du själv startat, via PID eller port, och kontrollera först att processen är din.
