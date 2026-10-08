import { Navigate, useOutletContext, useParams } from 'react-router-dom'

import { WIND_NAME, type Session } from './useLobby.ts'

export default function Game() {
  const { code = '' } = useParams()
  const { nickname, players, gameStatus, currentRound } = useOutletContext<Session>()

  if (gameStatus === 'waiting') return <Navigate to={`/lobby/${code}`} replace />

  const me = players.find((p) => p.nickname.toLowerCase() === nickname.toLowerCase())

  return (
    <div className="game">
      <h1>Rond {currentRound?.round_number}</h1>
      {me?.wind && <p className="muted">Din vind: {WIND_NAME[me.wind]}</p>}
    </div>
  )
}
