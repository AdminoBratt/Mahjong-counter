# Mahjong Score Tracker

Webbapp för realtids-poängräkning i Mahjong. Fyra spelare går in från sina
datorer (webbläsare), skapar/går med i en lobby via en 6-teckens kod och matar
in sina poäng rond för rond. All matematik sker i backend. Realtid via WebSockets.

## Stack
- Frontend: React + TypeScript (Vite), desktop-first för pc-webbläsare (`frontend/`)
- Backend: Python FastAPI + WebSockets (`backend/`)
- Lagring: INGEN databas. Allt spelstate hålls i minnet i backend (se "Lagring i minnet").
- Auth: gästinlogg via smeknamn, ingen e-post eller lösenord
- Deployment: frontend på Vercel, backend på Railway (ingen databastjänst behövs)

## Projektstruktur
```
Wizardworks/
  frontend/          # React + TypeScript (Vite)
  backend/           # FastAPI
  docs/              # referensdokument (se nedan)
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
- Desktop (pc-webbläsare) är primärt. Mobilanpassning prioriteras inte, men undvik att göra layouten omöjlig att använda på smal skärm.
- Poänglogiken (poäng, dubblingar, betalningar, vindrotation) ska ha enhetstester. Den är lätt att få fel.
- Inga e-postadresser samlas in.
- Hemligheter ska aldrig committas. Använd `.env`.
- UI-steg: använd `taste-skill`, men följ först designvalen under "Design" här i filen.
  Välj inga nya paletter eller typsnitt på egen hand.
- Skriv bara den kod ett steg kräver (ponytail). Poängmatematiken i backend ska ändå ha tester.

## Användbara kommandon
- Backend (från `backend/`): `uvicorn app.main:app --reload`
- Backend-tester (från `backend/`): `pytest`
- Frontend (från `frontend/`): `npm run dev`

## Miljövariabler (backend)
```
CORS_ORIGINS=http://localhost:5173
```

## Referens (läs vid behov, inte hela tiden)
- Faser och status: `docs/faser.md`
- Spelregler, poäng, dubblingar, betalningar, UI-flöde: `docs/spelregler.md`
- Datamodell (modeller i minnet): `docs/datamodell.md`
- WebSocket-events: `docs/events.md`

Läs `docs/spelregler.md` innan du rör poängberäkning, betalningar eller vindrotation.
Läs `docs/datamodell.md` innan du rör spelmodellerna eller `GameStore`.

## Design
Fylls i när första UI-steget är klart. Följ alltid dessa val i alla UI-steg.
- Stil, färgpalett och typsnitt: (ännu inte valda)
- Färger och typsnitt definieras som CSS-variabler i `frontend/src/styles/`.
  Hårdkoda aldrig färger eller typsnitt i komponenter, använd variablerna.

## Känd teknisk skuld
Medvetet uppskjutet, inte buggar.

- Prevailing wind (`Game.round_wind` / `Round.round_wind`) roterar inte ännu och är tills vidare fast `east`.
  Spelarnas individuella vindar roterar korrekt moturs. I riktig Mahjong byter rondens vind efter ett helt varv.
  Påverkar semantiken för dubblingen "3tal/4tal i rondens vind". Ingen felräkning nu eftersom
  `set_in_round_wind` är användarbekräftad indata i Vy 2. Uppskjuten till efter Fas 3.

## Lärdomar
Fylls på löpande. När Claude gör ett fel: skriv in rättelsen här som en kort regel.

-
