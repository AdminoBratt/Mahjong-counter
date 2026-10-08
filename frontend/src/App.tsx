import { BrowserRouter, Link, Outlet, Route, Routes, useParams } from 'react-router-dom'
import Game from './Game.tsx'
import Lobby from './Lobby.tsx'
import Start from './Start.tsx'
import { useLobby, type Session as SessionContext } from './useLobby.ts'

// Ligger kvar monterad mellan /lobby/:code och /game/:code, så socketen överlever sidbytet.
// Visar anslutningsläge och fel en gång; Lobby och Game renderar bara sitt innehåll.
function Session() {
  const { code = '' } = useParams()
  const lobby = useLobby(code)
  const { nickname, gameStatus, status } = lobby

  if (!nickname) {
    return (
      <div className="session-message">
        <h1>Lobby <span className="mono">{code}</span></h1>
        <p>Du har inte gått med i den här lobbyn.</p>
        <Link to="/">Gå med via startsidan</Link>
      </div>
    )
  }

  return (
    <>
      {status === 'connecting' && <p role="status" className="session-message">Ansluter…</p>}
      {status === 'closed' && (
        <div role="alert" className="session-message">
          <p className="error">Du är ansluten i en annan flik, eller anslutningen bröts.</p>
          <button className="primary" onClick={lobby.reconnect}>Anslut igen</button>
        </div>
      )}
      {typeof status === 'object' && (
        <div role="alert" className="session-message">
          <p className="error">{status.error}</p>
          <Link to="/">Till startsidan</Link>
        </div>
      )}
      {gameStatus !== null && <Outlet context={{ ...lobby, nickname, gameStatus } satisfies SessionContext} />}
    </>
  )
}

function NotFound() {
  return (
    <>
      <h1>Sidan finns inte</h1>
      <Link to="/">Till startsidan</Link>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <main>
        <Routes>
          <Route path="/" element={<Start />} />
          <Route element={<Session />}>
            <Route path="/lobby/:code" element={<Lobby />} />
            <Route path="/game/:code" element={<Game />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
