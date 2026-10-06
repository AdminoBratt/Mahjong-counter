# Faser och status

Följ ordningen. Ett steg i taget. Bocka av `[x]` när steget är klart och verifierat.

## Fas 1 — Fundament
- [ ] **1.1** Docker Compose med Postgres
- [ ] **1.2** FastAPI-skelett med databasanslutning (SQLAlchemy + Alembic)
- [ ] **1.3** Databasmigrationer (alla tabeller, se `datamodell.md`)
- [ ] **1.4** React + Vite + TypeScript-skelett med routing

## Fas 2 — Lobby
- [ ] **2.1** API: Skapa spel (generera lobby-kod)
- [ ] **2.2** API: Gå med i spel via kod + smeknamn
- [ ] **2.3** WebSocket: anslutning + `join_lobby`-event
- [ ] **2.4** UI: Startsida (skapa spel / gå med i spel)
- [ ] **2.5** UI: Lobby-vy (visar anslutna spelare, väntar på 4 st)
- [ ] **2.6** UI: Vindval (rond 1, varje spelare väljer sin startvind)

## Fas 3 — Poänginmatning
- [ ] **3.1** Backend: Poängberäkningsmodul (baspoäng + dubblingar)
- [ ] **3.2** Backend: Betalningslogik
- [ ] **3.3** Backend: Vindrotationslogik
- [ ] **3.4** API + WebSocket: `submit_score`, `round_complete`
- [ ] **3.5** UI: Vy 1, Baspoäng (desktop-optimerad)
- [ ] **3.6** UI: Vy 2, Allmänna dubblingar
- [ ] **3.7** UI: Vy 3, Mahjong-dubblingar (konditionell)
- [ ] **3.8** UI: Bekräftelseskärm med uträkning + betalningar

## Fas 4 — Spelvy (realtid)
- [ ] **4.1** UI: Aktiv spelvy (totalpoäng per spelare, aktuell vind, rondnummer)
- [ ] **4.2** UI: Poängkurva/graf (Chart.js eller Recharts)
- [ ] **4.3** WebSocket: live-uppdateringar till alla spelare
- [ ] **4.4** UI: Avsluta spel-knapp + slutresultat

## Fas 5 — Historik & Statistik
- [ ] **5.1** API: Hämta spelhistorik per smeknamn
- [ ] **5.2** API: Statistik (snittpoäng, vinster, etc.)
- [ ] **5.3** UI: Historikvy
- [ ] **5.4** UI: Statistikvy per spelare

## Fas 6 — Deployment
- [ ] **6.1** Frontend → Vercel
- [ ] **6.2** Backend + DB → Railway
- [ ] **6.3** Miljövariabler + secrets
- [ ] **6.4** CORS + produktionskonfiguration
