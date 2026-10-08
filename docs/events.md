# WebSocket-events

Alla SERVER → CLIENT-events broadcastas till ALLA spelare i lobbyn, utom `error`.

Anslutning: `ws(s)://<sidans adress>/ws`. Meddelanden är JSON med `type` plus fälten platt,
t.ex. `{"type": "join_lobby", "lobby_code": "ABC123", "nickname": "Anna"}`.
Första meddelandet måste vara `join_lobby` inom 10 sekunder. Samma smeknamn
(skiftlägesokänsligt) = återanslutning till samma spelare. En ny socket för samma
spelare ersätter den gamla, som stängs.

```
CLIENT → SERVER:
  join_lobby        { lobby_code, nickname }
  choose_wind       { wind }   # 'east' | 'south' | 'west' | 'north'
  submit_score      { round_id, score_input, draw }   # draw: bool, default false
  end_game          {}         # inte implementerat ännu

SERVER → CLIENT (broadcast till alla i lobby):
  lobby_update      { status, players: [{ id, nickname, seat_order, connected, wind, total_score }],
                      current_round }
                    # status: 'waiting' | 'active' | 'finished', wind: null tills vald
                    # current_round: null tills spelet startat, annars
                    #   { id, round_number, round_wind,   # round_wind är alltid 'east' tills vidare
                    #     conflict,                       # null | 'no_mahjong' | 'multiple_mahjong' | 'draw_disagreement'
                    #     submissions: { <player_id>: { draw, score_input } } }   # bara de som lämnat in
  round_complete    { round_id, round_number, winner_id,   # winner_id null = oavgjort
                      payments: { <player_id>: { base_points, doublings, final_points, payment_delta } },
                      new_totals: { <player_id>: int },
                      next_round_winds: { <player_id>: wind } }
  game_over         { final_standings, history }   # inte implementerat ännu

SERVER → CLIENT (bara till avsändaren):
  error             { code, message }
```

Efter `join_lobby` gäller:
- `choose_wind` tillåts bara när fyra spelare finns och `status` är `waiting`. Vinden får inte vara
  tagen av en annan spelare; byte till en ledig vind är tillåtet. Servern svarar alltid med
  `lobby_update` till alla, även när valet nekas (så att klienten synkas om).
- När alla fyra har valt sätts `status` till `active`. Därefter är vindarna låsta och nya smeknamn
  nekas med `game_started`.
- `submit_score` gäller den aktuella ronden (`current_round.id`). `score_input` är rådata enligt
  `ScoreInput` i `backend/app/scoring.py`, Mahjong anges i `score_input.mahjong`. En spelare får
  skicka in igen tills ronden är avslutad; den senaste gäller. Varje giltig inlämning ger
  `lobby_update` till alla. `submissions` syns för alla, så en spelare som återansluter får tillbaka
  sin egen inmatning.
- När ronden avslutas skickas `round_complete` först och sedan `lobby_update` med nästa rond.
  Kan ronden inte avslutas trots fyra inlämningar visas orsaken i `current_round.conflict`.
- Ogiltiga meddelanden (inte JSON, inte ett objekt, okänd `type`, binär ram, `choose_wind` med
  ogiltig vind) ignoreras. Socketen stängs inte och inget svar skickas.

`error.code` vid `join_lobby` (socketen stängs efteråt):
- `invalid_message`: första meddelandet saknas (timeout), är inte JSON eller inte `join_lobby`
- `invalid_nickname`: smeknamnet är tomt eller längre än 20 tecken
- `unknown_lobby`: lobbykoden finns inte
- `game_full`: fyra spelare finns redan och smeknamnet är nytt
- `game_started`: spelet har startat och smeknamnet är nytt

`error.code` vid `submit_score` (socketen stängs inte, ingen broadcast):
- `invalid_message`: fälten har fel typ (t.ex. `round_id` inte ett UUID, `score_input` inte ett objekt, `draw` inte bool)
- `not_active`: spelet har inte startat
- `wrong_round`: `round_id` är inte den aktuella ronden
- `invalid_score`: inmatningen bryter mot reglerna, eller både oavgjort och Mahjong
