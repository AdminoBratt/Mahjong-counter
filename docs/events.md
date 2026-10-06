# WebSocket-events

Alla SERVER → CLIENT-events broadcastas till ALLA spelare i lobbyn.

```
CLIENT → SERVER:
  join_lobby        { lobby_code, nickname }
  submit_score      { round_id, score_input }
  mark_mahjong      { round_id, mahjong_bonuses }
  end_game          {}

SERVER → CLIENT (broadcast till alla i lobby):
  lobby_update      { players, winds, current_round }
  score_update      { round_scores, total_scores }
  round_complete    { payments, new_totals, next_round_winds }
  game_over         { final_standings, history }
```
