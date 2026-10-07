# Datamodell (i minnet)

Ingen databas. Modellerna är vanliga Python-klasser (dataclasses eller Pydantic) i backend.
Alla spel ligger i en `GameStore` (t.ex. `dict[str, Game]` med lobby-kod som nyckel).
Allt försvinner när backend startar om. Se "Lagring i minnet" i CLAUDE.md.

Skissen nedan visar fält och relationer. Claude väljer exakt implementation, men håll
lagringen bakom ett litet gränssnitt (`GameStore`).

## Player
```
id          UUID
nickname    str
```

## Game
```
id            UUID
lobby_code    str (6 tecken, unik, t.ex. "ABC123")
status        'waiting' | 'active' | 'finished'
created_at    datetime
last_activity datetime   # används för att städa inaktiva spel
current_round int = 1
round_wind    'east' | 'south' | 'west' | 'north' = 'east'
players       list[GamePlayer]
rounds        list[Round]
```

## GamePlayer
```
id          UUID
player      Player
wind        'east' | 'south' | 'west' | 'north'
total_score int = 0
seat_order  int  # 1-4, avgör turordning
connected   bool # för återanslutning
```

## Round
```
id           UUID
round_number int
is_draw      bool = False   # oavgjort
winner_id    UUID | None    # GamePlayer.id
round_wind   'east' | 'south' | 'west' | 'north'
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
score_input     dict  # rådata från spelarens inmatning
```
