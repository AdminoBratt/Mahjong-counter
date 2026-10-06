# Mahjong Score Tracker

Webbapp för realtids-poängräkning i Mahjong. Fyra spelare går in från sina
datorer (webbläsare), skapar/går med i en lobby via en 6-teckens kod och matar in sina
poäng rond för rond. All matematik sker i backend. Realtid via WebSockets.

## Stack
- Frontend: React + TypeScript (Vite), desktop-first för pc-webbläsare (`frontend/`)
- Backend: Python FastAPI + SQLAlchemy + Alembic + WebSockets (`backend/`)
- Databas: PostgreSQL via Docker Compose
- Auth: gästinlogg via smeknamn, ingen e-post eller lösenord
- Deployment: frontend på Vercel, backend + DB på Railway

## Projektstruktur
```
MahjongW/
  frontend/          # React + TypeScript (Vite)
  backend/           # FastAPI
  docs/              # referensdokument (se nedan)
  docker-compose.yml
  CLAUDE.md
```

## Så jobbar vi
1. Ta ETT steg i taget från `docs/faser.md`, i ordning. Gör aldrig flera steg på en gång.
2. Skriv en kort plan (vilka filer påverkas, vad ska göras) och vänta på mitt OK innan du skriver kod.
3. Implementera och skriv/kör tester för det nya.
4. Granska din egen diff (`git diff`) innan commit och lista eventuella risker.
5. Jobba på en `feature/<kort-namn>`-branch. Conventional commits:
   `feat:` ny funktionalitet, `fix:` buggfix, `chore:` config/beroenden,
   `refactor:` omstrukturering utan ny funktionalitet.
6. Pusha och skapa PR med `gh pr create`.
7. Bocka av steget i `docs/faser.md` när det är klart och verifierat.

Om spelreglerna är oklara: fråga mig, gissa inte.

## Viktiga regler
- All poängmatematik sker ENBART i backend. Frontend skickar rådata (vad spelaren valt), backend beräknar allt.
- WebSocket-events broadcastas alltid till ALLA spelare i lobbyn.
- Desktop (pc-webbläsare) är primärt. Mobilanpassning prioriteras inte, men undvik att göra layouten omöjlig att använda på smal skärm.
- Poänglogiken (poäng, dubblingar, betalningar, vindrotation) ska ha enhetstester. Den är lätt att få fel.
- Inga e-postadresser samlas in.
- Hemligheter (SECRET_KEY m.m.) ska aldrig committas. Använd `.env`.
- UI-steg: använd `taste-skill`, men följ först designvalen under "Design" här i filen.
  Välj inga nya paletter eller typsnitt på egen hand.

## Användbara kommandon
- Starta databasen: `docker compose up -d`
- Titta i databasen: `docker compose exec db psql -U mahjong -d mahjong`
- Backend (från `backend/`): `uvicorn app.main:app --reload`
- Frontend (från `frontend/`): `npm run dev`
- Migrationer (från `backend/`): `alembic revision --autogenerate -m "<msg>"` och `alembic upgrade head`

## Miljövariabler (backend)
```
DATABASE_URL=postgresql://mahjong:mahjong@localhost:5432/mahjong
SECRET_KEY=<genereras>
CORS_ORIGINS=http://localhost:5173
```

## Referens (läs vid behov, inte hela tiden)
- Faser och status: `docs/faser.md`
- Spelregler, poäng, dubblingar, betalningar, UI-flöde: `docs/spelregler.md`
- Datamodell: `docs/datamodell.md`
- WebSocket-events: `docs/events.md`

Läs `docs/spelregler.md` innan du rör poängberäkning, betalningar eller vindrotation.
Läs `docs/datamodell.md` innan du rör modeller eller migrationer.

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
