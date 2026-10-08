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
- [x] **2.5** UI: Lobby-vy (visar anslutna spelare, väntar på 4 st)
  - Kom ihåg: härled /ws-adressen från VITE_API_URL (http→ws, https→wss).
- [x] **2.6** UI: Vindval (rond 1, varje spelare väljer sin startvind)

## Fas 3 — Poänginmatning
- [x] **3.1** Backend: Poängberäkningsmodul (baspoäng + dubblingar)
- [x] **3.2** Backend: Betalningslogik
- [x] **3.3** Backend: Vindrotationslogik
- [x] **3.4** API + WebSocket: `submit_score`, `round_complete`
  - [x] **3.4a** Backend: rondflöde i `GameStore` (`submit_score`, oavgjort, konflikter) + tester
  - [x] **3.4b** WebSocket: `submit_score`, `round_complete`, `current_round` i `lobby_update`, lås per lobby
    - Kom ihåg: test att `round_complete` kommer före nya `lobby_update`; tillfälligt skript (committas inte)
      som spelar en rond med fyra spelare mot en riktig server.
- [x] **3.5** UI: Vy 1, Baspoäng (desktop-optimerad)
- [x] **3.6** UI: Vy 2, Allmänna dubblingar
- [x] **3.7** UI: Vy 3, Mahjong-dubblingar (konditionell)
- [x] **3.8** UI: Bekräftelseskärm med uträkning + betalningar
  - [x] **3.8a** Skicka in och vänta: sammanfattning, uträkning från servern, konflikter, serverfel, ställning i huvudet
    - Kom ihåg: testa att en omladdning mitt i en rond fyller i formuläret igen från serverns `submissions` (egen inlämning, även oavgjort).
  - [x] **3.8b** Rondresultat: `last_round` i `lobby_update`, betalningar, nya totaler, vind i ronden och nästa vindar, knappen "Nästa rond"
- [x] **3.9** Direkt inmatning av slutpoäng ("Hur slutade ronden?" som eget steg, "Jag kan inte räkna" leder till Vy 1–3)
  - [x] **3.9a** Backend: `submit_score` med `final_points` + `mahjong`, validering (heltal, jämnt, ≥ 0, ≥ 20 vid Mahjong),
    `null` i baspoäng/dubblingar, `mahjong` i `submissions`, dokumentation och tester
  - [x] **3.9b** Frontend: utfallssteg, fältet "Dina poäng för ronden", "Jag kan inte räkna", "–" i väntläget och rondresultatet
    - Kom ihåg: etikett "Dina poäng för ronden", hjälptext "Poängen på din hand. Det är inte vad du får eller betalar,
      det räknar servern ut." Knappen visar talet ("Skicka 1 280", sv-SE) och talet ekas stort under fältet.
      Udda tal avvisas även i frontend. "Ändra min inmatning" följer förra inlämningens läge.

## Fas 4 — Spelvy (realtid)
- [x] **4.1** UI: Aktiv spelvy (totalpoäng per spelare, aktuell vind, rondnummer)
- [ ] **4.2** UI: Poängkurva/graf (Chart.js eller Recharts)
- [x] **4.3** WebSocket: live-uppdateringar till alla spelare
- [ ] **4.4** UI: Avsluta spel-knapp + slutresultat
- [ ] **4.5** Backend: Städa bort inaktiva och avslutade spel ur minnet efter en tid
  - Kom ihåg: stäng öppna sockets i `connections` och släpp låset i `locks` för spelet som städas bort.

## Fas 5 — Deployment (en tjänst på Railway, görs före Fas 3)
- [x] **5.1** Backend: API under `/api`, FastAPI serverar byggd frontend med fallback till `index.html`
- [x] **5.2** Frontend: tom `VITE_API_URL` = samma adress som sidan (`wss://` i produktion), `localhost:8000` lokalt
- [x] **5.3** Backend: kontrollera `Origin` på `/ws` (samma host, `X-Forwarded-Host` eller `CORS_ORIGINS`)
- [x] **5.4** Dockerfile i två steg + `.dockerignore`, verifierat med `docker build` / `docker run`
- [x] **5.5** Railway: deploy från GitHub, domän, healthcheck `/api/health`, en replika, ingen sömn
  - Kom ihåg: varje merge till `main` startar om tjänsten och raderar pågående spel.
