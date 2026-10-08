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
status        'waiting' | 'active' | 'finished'
created_at    datetime
last_activity datetime   # används för att städa inaktiva spel
players       list[GamePlayer]
rounds        list[Round]  # sista = aktuell rond, skapas när status blir 'active'
```
Rondnummer och rondens vind läses från `rounds[-1]`.

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

## RoundScore
```
game_player_id  UUID
base_points     int
doublings       int
final_points    int   # base_points × 2^doublings
payment_delta   int   # netto efter betalningar (kan vara negativt)
did_mahjong     bool = False
draw            bool = False  # spelaren har valt oavgjort
score_input     dict  # rådata från spelarens inmatning
```
