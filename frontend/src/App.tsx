import { BrowserRouter, Link, Route, Routes, useParams } from 'react-router-dom'
import Start from './Start.tsx'

// Platshållare, ersätts i steg 2.5 och 4.1.
function Lobby() {
  const { code } = useParams()
  return <h1>Lobby <span className="mono">{code}</span></h1>
}

function Game() {
  const { code } = useParams()
  return <h1>Spel <span className="mono">{code}</span></h1>
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
          <Route path="/lobby/:code" element={<Lobby />} />
          <Route path="/game/:code" element={<Game />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
