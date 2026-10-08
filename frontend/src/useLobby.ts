import { useEffect, useRef, useState } from 'react'

import { WS_URL } from './api.ts'
import type { ScoreInput } from './draft.ts'

// Efter dessa koder går det inte att gå med igen med samma kod/namn.
const STALE_SESSION_CODES = ['unknown_lobby', 'game_full', 'game_started', 'invalid_nickname']

export type Wind = 'east' | 'south' | 'west' | 'north'
export type Player = {
  id: string
  nickname: string
  seat_order: number
  connected: boolean
  wind: Wind | null
  total_score: number
}
export type GameStatus = 'waiting' | 'active' | 'finished'
// Uträkningen kommer från servern och visas som den är. Direkt slutpoäng: score_input, base_points och doublings null.
export type RoundSubmission = {
  draw: boolean
  mahjong: boolean
  score_input: Partial<ScoreInput> | null
  base_points: number | null
  doublings: number | null
  final_points: number
}
export type Conflict = 'no_mahjong' | 'multiple_mahjong' | 'draw_disagreement'
export type CurrentRound = {
  id: string
  round_number: number
  round_wind: Wind
  conflict: Conflict | null
  submissions: Record<string, RoundSubmission>
}
// Senast avslutade ronden, från lobby_update. Samma innehåll live och efter omladdning.
export type RoundResult = {
  round_id: string
  round_number: number
  round_wind: Wind
  winner_id: string | null // null = oavgjort
  payments: Record<
    string,
    { wind: Wind; base_points: number | null; doublings: number | null; final_points: number; payment_delta: number }
  >
  new_totals: Record<string, number>
  next_round_winds: Record<string, Wind>
}
export type Status = 'connecting' | 'open' | 'closed' | { error: string }

export const WINDS: [Wind, string][] = [
  ['east', 'Öst'],
  ['south', 'Syd'],
  ['west', 'Väst'],
  ['north', 'Nord'],
]
export const WIND_NAME = Object.fromEntries(WINDS) as Record<Wind, string>

// En socket per lobby. Används av layout-routen så att den överlever bytet lobby → spel.
export function useLobby(code: string) {
  // Läses en gång, så att felmeddelandet syns kvar när sessionen rensas nedan.
  const [nickname] = useState(() =>
    sessionStorage.getItem('lobby_code') === code ? sessionStorage.getItem('nickname') : null,
  )
  const [players, setPlayers] = useState<Player[]>([])
  const [gameStatus, setGameStatus] = useState<GameStatus | null>(null) // null tills första lobby_update
  const [currentRound, setCurrentRound] = useState<CurrentRound | null>(null)
  const [lastRound, setLastRound] = useState<RoundResult | null>(null)
  // Fel på ett meddelande efter join (t.ex. submit_score). Socketen lever vidare.
  const [actionError, setActionError] = useState<{ code: string; message: string } | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const [status, setStatus] = useState<Status>('connecting')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!nickname) return
    let current = true // false efter cleanup, så gamla sockets (t.ex. StrictMode) ignoreras
    let gotError = false
    let joined = false // efter första lobby_update är fel inte längre join-fel
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws
    ws.onopen = () => ws.send(JSON.stringify({ type: 'join_lobby', lobby_code: code, nickname }))
    ws.onmessage = (e) => {
      if (!current) return
      const msg = JSON.parse(e.data)
      if (msg.type === 'lobby_update') {
        joined = true
        setPlayers(msg.players)
        setGameStatus(msg.status)
        setCurrentRound(msg.current_round)
        setLastRound(msg.last_round) // round_complete ignoreras: last_round är en kodväg för live och omladdning
        setStatus('open')
      } else if (msg.type === 'error' && joined) {
        setActionError({ code: msg.code, message: msg.message })
      } else if (msg.type === 'error') {
        gotError = true
        if (STALE_SESSION_CODES.includes(msg.code)) {
          sessionStorage.removeItem('lobby_code')
          sessionStorage.removeItem('nickname')
        }
        setStatus({ error: msg.message })
      }
    }
    ws.onclose = () => {
      if (current && !gotError) setStatus('closed')
    }
    return () => {
      current = false
      ws.close()
    }
  }, [code, nickname, attempt])

  function send(msg: object) {
    setActionError(null)
    wsRef.current?.send(JSON.stringify(msg))
  }

  function reconnect() {
    setStatus('connecting')
    setAttempt((n) => n + 1)
  }

  return { nickname, players, gameStatus, currentRound, lastRound, actionError, status, send, reconnect }
}

// Det som layout-routen skickar till Lobby och Game. Barnen renderas först när gameStatus är satt.
export type Session = ReturnType<typeof useLobby> & { nickname: string; gameStatus: GameStatus }
