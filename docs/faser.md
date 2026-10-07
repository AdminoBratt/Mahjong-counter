# Faser och status

Följ ordningen. Ett steg i taget. Bocka av `[x]` när steget är klart och verifierat.
Ingen databas: spelstate hålls i minnet (se CLAUDE.md). Ingen historik eller statistik.

## Fas 1 — Fundament
- [x] **1.1** FastAPI-skelett (struktur, health-endpoint, CORS, `GameStore` i minnet, pytest)
- [x] **1.2** React + Vite + TypeScript-skelett med routing

## Fas 2 — Lobby
- [x] **2.1** API: Skapa spel (generera lobby-kod, lagras i `GameStore`)
- [x] **2.2** API: Gå med i spel via kod + smeknamn
- [x] **2.3** WebSocket: anslutning + `join_lobby`-event, inklusive återanslutning med kod + smeknamn
- [x] **2.4** UI: Startsida (skapa spel / gå med i spel)
- [ ] **2.5** UI: Lobby-vy (visar anslutna spelare, väntar på 4 st)
  - Kom ihåg: härled /ws-adressen från VITE_API_URL (http→ws, https→wss).
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
- [ ] **4.5** Backend: Städa bort inaktiva och avslutade spel ur minnet efter en tid
  - Kom ihåg: stäng öppna sockets i `connections` för spelet som städas bort.

## Fas 5 — Deployment
- [ ] **5.1** Frontend → Vercel
  - Kom ihåg: Vercel behöver en rewrite i `vercel.json` som skickar alla adresser till `index.html`. Annars får direktlänkar som `/lobby/ABC123` 404 där.
- [ ] **5.2** Backend → Railway (en instans, ingen databas)
- [ ] **5.3** Miljövariabler
- [ ] **5.4** CORS + produktionskonfiguration, frontend ansluter med `wss://` till backendens adress
  - Kom ihåg: CORS gäller inte WebSockets. Kontrollera `Origin`-headern mot `CORS_ORIGINS` i `/ws`.
