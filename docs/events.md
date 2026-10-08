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
  submit_score      { round_id, score_input, draw }   # Vy 1–3 eller oavgjort. draw: bool, default false
                    { round_id, final_points, mahjong }  # slutpoäng som spelaren räknat själv, mahjong: bool, default false
  end_game          {}         # inte implementerat ännu

SERVER → CLIENT (broadcast till alla i lobby):
  lobby_update      { status, players: [{ id, nickname, seat_order, connected, wind, total_score }],
                      current_round, last_round }
                    # status: 'waiting' | 'active' | 'finished', wind: null tills vald
                    # current_round: null tills spelet startat, annars
                    #   { id, round_number, round_wind,   # round_wind är alltid 'east' tills vidare
                    #     conflict,                       # null | 'no_mahjong' | 'multiple_mahjong' | 'draw_disagreement'
                    #     submissions: { <player_id>: { draw, mahjong, score_input,       # bara de som lämnat in
                    #                                   base_points, doublings, final_points } } }
                    #       # direkt slutpoäng: score_input, base_points och doublings är null
                    # last_round: null tills första ronden avslutats, annars senast avslutade ronden
                    #   med samma fält som round_complete (utan type)
                    # score_history: { <player_id>: [int, ...] }   # total efter varje avslutad rond
                    #   index = rondnummer, [0] = start (0). Oavgjord rond = samma värde som förra.
                    #   Sista värdet = spelarens total_score. En pågående rond syns inte.
  round_complete    { round_id, round_number, round_wind, winner_id,   # winner_id null = oavgjort
                      payments: { <player_id>: { wind,   # spelarens vind i ronden
                                                 base_points, doublings, final_points, payment_delta } },
                                                 # base_points/doublings null = slutpoängen angiven direkt
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
- `submit_score` gäller den aktuella ronden (`current_round.id`). Exakt en av `score_input` och
  `final_points` skickas. `score_input` är rådata enligt `ScoreInput` i `backend/app/scoring.py`, och
  Mahjong anges då i `score_input.mahjong`. `final_points` är en slutpoäng som spelaren räknat själv
  (heltal, jämnt, minst 0, minst 20 vid Mahjong), och Mahjong anges då i `mahjong`. Backend räknar inte om
  den, men betalningar, totaler och vindrotation räknas alltid i backend. Oavgjort skickas som
  `{draw: true, score_input: {}}`. `submissions[*].mahjong` visar om spelaren angett Mahjong i båda lägena. En spelare får
  skicka in igen tills ronden är avslutad; den senaste gäller. Varje giltig inlämning ger
  `lobby_update` till alla. `submissions` syns för alla, så en spelare som återansluter får tillbaka
  sin egen inmatning. `base_points`, `doublings` och `final_points` är serverns uträkning av
  inlämningen (vid direkt slutpoäng är de två första `null` och `final_points` spelarens tal); klienten
  visar dem som de är och räknar inget själv.
- När ronden avslutas skickas `round_complete` först och sedan `lobby_update` med nästa rond.
  Kan ronden inte avslutas trots fyra inlämningar visas orsaken i `current_round.conflict`.
- `last_round` byggs av samma funktion som `round_complete`, så resultatet är identiskt live och efter
  omladdning. Klienten läser bara `last_round`; `round_complete` skickas kvar för protokollet.
- `score_history` räknas i backend ur rondresultaten, med samma kod live och efter omladdning.
  Klienten ritar bara talen. Efter 30 ronder är fältet ungefär 1 KB.
- Ogiltiga meddelanden (inte JSON, inte ett objekt, okänd `type`, binär ram, `choose_wind` med
  ogiltig vind) ignoreras. Socketen stängs inte och inget svar skickas.

`error.code` vid `join_lobby` (socketen stängs efteråt):
- `invalid_message`: första meddelandet saknas (timeout), är inte JSON eller inte `join_lobby`
- `invalid_nickname`: smeknamnet är tomt eller längre än 20 tecken
- `unknown_lobby`: lobbykoden finns inte
- `game_full`: fyra spelare finns redan och smeknamnet är nytt
- `game_started`: spelet har startat och smeknamnet är nytt

`error.code` vid `submit_score` (socketen stängs inte, ingen broadcast):
- `invalid_message`: fälten har fel typ (t.ex. `round_id` inte ett UUID, `score_input` inte ett objekt, `draw` inte bool,
  `final_points` inte ett heltal (bool och decimaltal avvisas), `mahjong` inte bool), både eller ingen av `score_input`
  och `final_points`, `final_points` med `draw: true`, eller `mahjong` med `score_input`
- `not_active`: spelet har inte startat
- `wrong_round`: `round_id` är inte den aktuella ronden
- `invalid_score`: inmatningen bryter mot reglerna, eller både oavgjort och Mahjong. För `final_points`:
  negativt, udda, eller under 20 med `mahjong: true`
