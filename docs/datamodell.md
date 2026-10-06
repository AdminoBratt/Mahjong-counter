# Datamodell

## Player
```sql
id          UUID PRIMARY KEY
nickname    TEXT NOT NULL
created_at  TIMESTAMP
```

## Game
```sql
id            UUID PRIMARY KEY
lobby_code    CHAR(6) UNIQUE NOT NULL  -- t.ex. "ABC123"
status        ENUM('waiting', 'active', 'finished')
created_at    TIMESTAMP
current_round INT DEFAULT 1
round_wind    ENUM('east','south','west','north') DEFAULT 'east'
```

## GamePlayer
```sql
id          UUID PRIMARY KEY
game_id     UUID REFERENCES Game
player_id   UUID REFERENCES Player
wind        ENUM('east','south','west','north')
total_score INT DEFAULT 0
seat_order  INT  -- 1-4, avgör turordning
```

## Round
```sql
id           UUID PRIMARY KEY
game_id      UUID REFERENCES Game
round_number INT
is_draw      BOOLEAN DEFAULT FALSE  -- oavgjort
winner_id    UUID REFERENCES GamePlayer NULL
round_wind   ENUM('east','south','west','north')
```

## RoundScore
```sql
id              UUID PRIMARY KEY
round_id        UUID REFERENCES Round
game_player_id  UUID REFERENCES GamePlayer
base_points     INT
doublings       INT
final_points    INT   -- base_points × 2^doublings
payment_delta   INT   -- netto efter betalningar (kan vara negativt)
did_mahjong     BOOLEAN DEFAULT FALSE
score_input     JSONB  -- rådata från spelarens inmatning
```
