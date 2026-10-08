# Datamodell (i minnet)

Ingen databas. Modellerna är vanliga Python-klasser (dataclasses eller Pydantic) i backend.
Alla spel ligger i en `GameStore` (t.ex. `dict[str, Game]` med lobby-kod som nyckel).
Allt försvinner när backend startar om. Se "Lagring i minnet" i CLAUDE.md.

Skissen nedan visar fält och relationer. Claude väljer exakt implementation, men håll
lagringen bakom ett litet gränssnitt (`GameStore`).

## Game
```
id            UUID
lobby_code    str (6 tecken, unik, t.ex. "ABC123")
status        'waiting' | 'active' | 'finished'   # 'finished' sätts av end_game (bara skaparen)
created_at    datetime
last_activity datetime   # senast rörd: create, join (inte till avslutat spel), godkänt choose_wind/submit_score, end_game
disconnected_since datetime | None   # när sista socketen stängdes, None medan någon är ansluten
players       list[GamePlayer]
rounds        list[Round]  # sista = aktuell rond, skapas när status blir 'active'
```
Rondnummer och rondens vind läses från `rounds[-1]`. Skaparen är spelaren med `seat_order` 1.
`GameStore.is_stale(game, now)` avgör om spelet ska städas bort (tider i docs/events.md, "Städning").
Alla tider är UTC-datetime med tidszon (`_now()`).
`Game.standings()` ger slutställningen (placering, spelare). En rond som pågick när spelet avslutades
ligger kvar i `rounds` men räknas inte och visas inte.

## GamePlayer
`Player` och `GamePlayer` är sammanslagna: en spelare finns bara i ett spel.
```
id          UUID
nickname    str  # unik per spel, jämförs med casefold(); samma namn = återanslutning
seat_order  int  # 1-4, i den ordning spelarna gick med
wind        'east' | 'south' | 'west' | 'north' | None  # aktuell vind, None tills startvinden är vald
total_score int = 0
connected   bool                                 # för återanslutning, läggs till i 2.3
```

## Round
```
id           UUID
round_number int
is_draw      bool = False   # oavgjort
winner_id    UUID | None    # GamePlayer.id
round_wind   'east' | 'south' | 'west' | 'north' = 'east'  # fast tills vidare, se teknisk skuld
scores       list[RoundScore]
```
Poänghistoriken (`score_history` i `lobby_update`) lagras inte. `Game.score_history()` härleder den ur
`payment_delta` i avslutade ronder (`Round.completed`: `winner_id` satt eller `is_draw`).

## RoundScore
```
game_player_id  UUID
base_points     int | None   # None = slutpoängen angiven direkt av spelaren
doublings       int | None   # None = slutpoängen angiven direkt av spelaren
final_points    int   # base_points × 2^doublings, eller angiven direkt av spelaren
payment_delta   int   # netto efter betalningar (kan vara negativt)
did_mahjong     bool = False
draw            bool = False  # spelaren har valt oavgjort
score_input     dict | None  # rådata från spelarens inmatning, None = slutpoängen angiven direkt
wind            Wind  # spelarens vind i ronden (GamePlayer.wind har roterats när ronden avslutats)
```
