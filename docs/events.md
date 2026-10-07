# WebSocket-events

Alla SERVER → CLIENT-events broadcastas till ALLA spelare i lobbyn, utom `error`.

Anslutning: `ws://<backend>/ws`. Meddelanden är JSON med `type` plus fälten platt,
t.ex. `{"type": "join_lobby", "lobby_code": "ABC123", "nickname": "Anna"}`.
Första meddelandet måste vara `join_lobby` inom 10 sekunder. Samma smeknamn
(skiftlägesokänsligt) = återanslutning till samma spelare. En ny socket för samma
spelare ersätter den gamla, som stängs.

```
CLIENT → SERVER:
  join_lobby        { lobby_code, nickname }
  choose_wind       { wind }   # 'east' | 'south' | 'west' | 'north'
  submit_score      { round_id, score_input }
  mark_mahjong      { round_id, mahjong_bonuses }
  end_game          {}

SERVER → CLIENT (broadcast till alla i lobby):
  lobby_update      { status, players: [{ id, nickname, seat_order, connected, wind }] }
                    # status: 'waiting' | 'active' | 'finished', wind: null tills vald
                    # current_round läggs till i fas 3
  score_update      { round_scores, total_scores }
  round_complete    { payments, new_totals, next_round_winds }
  game_over         { final_standings, history }

SERVER → CLIENT (bara till den som anslöt, sedan stängs socketen):
  error             { code, message }
```

Efter `join_lobby` gäller:
- `choose_wind` tillåts bara när fyra spelare finns och `status` är `waiting`. Vinden får inte vara
  tagen av en annan spelare; byte till en ledig vind är tillåtet. Servern svarar alltid med
  `lobby_update` till alla, även när valet nekas (så att klienten synkas om).
- När alla fyra har valt sätts `status` till `active`. Därefter är vindarna låsta och nya smeknamn
  nekas med `game_started`.
- Ogiltiga meddelanden (inte JSON, inte ett objekt, okänd `type`, binär ram) ignoreras.
  Socketen stängs inte och inget svar skickas.

`error.code` (bara vid `join_lobby`):
- `invalid_message`: första meddelandet saknas (timeout), är inte JSON eller inte `join_lobby`
- `invalid_nickname`: smeknamnet är tomt eller längre än 20 tecken
- `unknown_lobby`: lobbykoden finns inte
- `game_full`: fyra spelare finns redan och smeknamnet är nytt
- `game_started`: spelet har startat och smeknamnet är nytt
