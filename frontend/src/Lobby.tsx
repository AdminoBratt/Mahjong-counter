import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const WS_URL = API_URL.replace(/^http/, 'ws') + '/ws'

// Efter dessa koder går det inte att gå med igen med samma kod/namn.
const STALE_SESSION_CODES = ['unknown_lobby', 'game_full', 'game_started', 'invalid_nickname']

type Wind = 'east' | 'south' | 'west' | 'north'
type Player = { id: string; nickname: string; seat_order: number; connected: boolean; wind: Wind | null }
type Status = 'connecting' | 'open' | 'closed' | { error: string }

const WINDS: [Wind, string][] = [
  ['east', 'Öst'],
  ['south', 'Syd'],
  ['west', 'Väst'],
  ['north', 'Nord'],
]
const WIND_NAME = Object.fromEntries(WINDS) as Record<Wind, string>

export default function Lobby() {
  const { code = '' } = useParams()
  // Läses en gång, så att felmeddelandet syns kvar när sessionen rensas nedan.
  const [nickname] = useState(() =>
    sessionStorage.getItem('lobby_code') === code ? sessionStorage.getItem('nickname') : null,
  )
  const [players, setPlayers] = useState<Player[]>([])
  const [gameStatus, setGameStatus] = useState<'waiting' | 'active' | 'finished'>('waiting')
  const wsRef = useRef<WebSocket | null>(null)
  const [status, setStatus] = useState<Status>('connecting')
  const [attempt, setAttempt] = useState(0)
  const [copied, setCopied] = useState<'ok' | 'fail' | null>(null)

  useEffect(() => {
    if (!nickname) return
    let current = true // false efter cleanup, så gamla sockets (t.ex. StrictMode) ignoreras
    let gotError = false
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws
    ws.onopen = () => ws.send(JSON.stringify({ type: 'join_lobby', lobby_code: code, nickname }))
    ws.onmessage = (e) => {
      if (!current) return
      const msg = JSON.parse(e.data)
      if (msg.type === 'lobby_update') {
        setPlayers(msg.players)
        setGameStatus(msg.status)
        setStatus('open')
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

  function chooseWind(wind: Wind) {
    wsRef.current?.send(JSON.stringify({ type: 'choose_wind', wind }))
  }

  function reconnect() {
    setStatus('connecting')
    setAttempt((n) => n + 1)
  }

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code)
      setCopied('ok')
    } catch {
      setCopied('fail')
    }
  }

  if (!nickname) {
    return (
      <div className="lobby">
        <h1>Lobby <span className="mono">{code}</span></h1>
        <p>Du har inte gått med i den här lobbyn.</p>
        <Link to="/">Gå med via startsidan</Link>
      </div>
    )
  }

  const seats = [1, 2, 3, 4].map((i) => players.find((p) => p.seat_order === i))
  const missing = 4 - players.length
  const isMe = (p: Player) => p.nickname.toLowerCase() === nickname.toLowerCase()
  const chosen = players.filter((p) => p.wind).length
  const started = gameStatus !== 'waiting'

  return (
    <div className="lobby">
      <h1>Lobby</h1>

      <div className="lobby-code">
        <span className="mono">{code}</span>
        <button className="secondary" onClick={copyCode}>
          {copied === 'ok' ? 'Kopierat' : 'Kopiera kod'}
        </button>
      </div>
      {copied === 'fail' && <p role="alert" className="error">Kunde inte kopiera. Markera koden och kopiera själv.</p>}

      <ol className="seats">
        {seats.map((p, i) => (
          <li key={i} className={p ? 'seat' : 'seat empty'}>
            {p ? (
              <>
                <span>
                  {p.nickname}
                  {isMe(p) && <span className="muted"> (du)</span>}
                </span>
                {missing === 0 && (
                  <span className={p.wind ? 'seat-wind' : 'seat-wind muted'}>
                    {p.wind ? WIND_NAME[p.wind] : 'Väljer vind…'}
                  </span>
                )}
                <span className={p.connected ? 'online' : 'muted'}>
                  {p.connected ? 'Ansluten' : 'Frånkopplad'}
                </span>
              </>
            ) : (
              <span className="muted">Väntar på spelare…</span>
            )}
          </li>
        ))}
      </ol>

      {missing === 0 && (
        <fieldset className="winds" disabled={started || status !== 'open'}>
          <legend>{started ? 'Startvindar' : 'Välj din startvind'}</legend>
          {WINDS.map(([wind, name]) => {
            const owner = players.find((p) => p.wind === wind)
            const mine = owner !== undefined && isMe(owner)
            return (
              <label key={wind} className={mine ? 'wind mine' : 'wind'}>
                <input
                  type="radio"
                  name="wind"
                  value={wind}
                  checked={mine}
                  disabled={owner !== undefined && !mine}
                  onChange={() => chooseWind(wind)}
                />
                <span>
                  {name}
                  {owner && <span className="muted">{mine ? 'Din vind' : owner.nickname}</span>}
                </span>
              </label>
            )
          })}
        </fieldset>
      )}

      <p role="status" aria-atomic="true">
        {status === 'connecting' && 'Ansluter…'}
        {status === 'open' &&
          (missing > 0
            ? `${players.length} av 4 spelare. Väntar på ${missing} till.`
            : started
              ? 'Alla vindar valda. Spelet startar.'
              : `Välj startvind. ${chosen} av 4 har valt.`)}
      </p>

      {status === 'closed' && (
        <div role="alert" className="lobby-problem">
          <p className="error">Du är ansluten i en annan flik, eller anslutningen bröts.</p>
          <button className="primary" onClick={reconnect}>Anslut igen</button>
        </div>
      )}
      {typeof status === 'object' && (
        <div role="alert" className="lobby-problem">
          <p className="error">{status.error}</p>
          <Link to="/">Till startsidan</Link>
        </div>
      )}
    </div>
  )
}
