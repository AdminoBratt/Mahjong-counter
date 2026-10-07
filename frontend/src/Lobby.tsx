import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const WS_URL = API_URL.replace(/^http/, 'ws') + '/ws'

// Efter dessa koder går det inte att gå med igen med samma kod/namn.
const STALE_SESSION_CODES = ['unknown_lobby', 'game_full', 'game_started', 'invalid_nickname']

type Player = { id: string; nickname: string; seat_order: number; connected: boolean }
type Status = 'connecting' | 'open' | 'closed' | { error: string }

export default function Lobby() {
  const { code = '' } = useParams()
  // Läses en gång, så att felmeddelandet syns kvar när sessionen rensas nedan.
  const [nickname] = useState(() =>
    sessionStorage.getItem('lobby_code') === code ? sessionStorage.getItem('nickname') : null,
  )
  const [players, setPlayers] = useState<Player[]>([])
  const [status, setStatus] = useState<Status>('connecting')
  const [attempt, setAttempt] = useState(0)
  const [copied, setCopied] = useState<'ok' | 'fail' | null>(null)

  useEffect(() => {
    if (!nickname) return
    let current = true // false efter cleanup, så gamla sockets (t.ex. StrictMode) ignoreras
    let gotError = false
    const ws = new WebSocket(WS_URL)
    ws.onopen = () => ws.send(JSON.stringify({ type: 'join_lobby', lobby_code: code, nickname }))
    ws.onmessage = (e) => {
      if (!current) return
      const msg = JSON.parse(e.data)
      if (msg.type === 'lobby_update') {
        setPlayers(msg.players)
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
                  {p.nickname.toLowerCase() === nickname.toLowerCase() && <span className="muted"> (du)</span>}
                </span>
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

      <p role="status" aria-atomic="true">
        {status === 'connecting' && 'Ansluter…'}
        {status === 'open' &&
          (missing > 0
            ? `${players.length} av 4 spelare. Väntar på ${missing} till.`
            : 'Alla fyra är här.')}
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
