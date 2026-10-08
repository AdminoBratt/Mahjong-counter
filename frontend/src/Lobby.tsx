import { useState } from 'react'
import { Navigate, useOutletContext, useParams } from 'react-router-dom'

import { WINDS, WIND_NAME, type Player, type Session, type Wind } from './useLobby.ts'

export default function Lobby() {
  const { code = '' } = useParams()
  const { nickname, players, gameStatus, status, send } = useOutletContext<Session>()
  const [copied, setCopied] = useState<'ok' | 'fail' | null>(null)

  if (gameStatus !== 'waiting') return <Navigate to={`/game/${code}`} replace />

  function chooseWind(wind: Wind) {
    send({ type: 'choose_wind', wind })
  }

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code)
      setCopied('ok')
    } catch {
      setCopied('fail')
    }
  }

  const seats = [1, 2, 3, 4].map((i) => players.find((p) => p.seat_order === i))
  const missing = 4 - players.length
  const isMe = (p: Player) => p.nickname.toLowerCase() === nickname.toLowerCase()
  const chosen = players.filter((p) => p.wind).length

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
        <fieldset className="winds" disabled={status !== 'open'}>
          <legend>Välj din startvind</legend>
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
        {status === 'open' &&
          (missing > 0
            ? `${players.length} av 4 spelare. Väntar på ${missing} till.`
            : `Välj startvind. ${chosen} av 4 har valt.`)}
      </p>
    </div>
  )
}
