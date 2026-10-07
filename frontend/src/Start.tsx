import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { API_URL } from './api.ts'

type Errors = { nickname?: string; code?: string; create?: string; join?: string }

export default function Start() {
  const navigate = useNavigate()
  const [nickname, setNickname] = useState('')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState<'create' | 'join' | null>(null)
  const [errors, setErrors] = useState<Errors>({})
  const nicknameRef = useRef<HTMLInputElement>(null)
  const codeRef = useRef<HTMLInputElement>(null)

  async function submit(kind: 'create' | 'join') {
    if (busy) return
    const name = nickname.trim()
    if (!name) {
      setErrors({ nickname: 'Ange ett smeknamn' })
      return nicknameRef.current?.focus()
    }
    if (kind === 'join' && code.length !== 6) {
      setErrors({ code: 'Lobbykoden har 6 tecken' })
      return codeRef.current?.focus()
    }

    setErrors({})
    setBusy(kind)
    try {
      let lobbyCode = code
      if (kind === 'create') {
        const res = await fetch(`${API_URL}/api/games`, { method: 'POST' })
        if (!res.ok) throw new Error()
        lobbyCode = (await res.json()).lobby_code
      }
      const res = await fetch(`${API_URL}/api/games/${encodeURIComponent(lobbyCode)}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nickname: name }),
      })
      if (res.ok) {
        const data = await res.json()
        // Lobbyvyn (2.5) läser dessa för att ansluta och återansluta till /ws.
        sessionStorage.setItem('lobby_code', data.lobby_code)
        sessionStorage.setItem('nickname', name)
        navigate(`/lobby/${data.lobby_code}`)
        return
      }
      if (kind === 'create') {
        setErrors({ create: 'Spelet skapades men det gick inte att gå med i det. Försök igen.' })
      } else if (res.status === 404 || res.status === 409) {
        setErrors({ code: (await res.json()).detail })
        codeRef.current?.focus()
      } else if (res.status === 422) {
        setErrors({ nickname: 'Smeknamnet måste vara 1–20 tecken' })
        nicknameRef.current?.focus()
      } else {
        throw new Error()
      }
    } catch {
      setErrors({ [kind]: 'Kunde inte nå servern. Försök igen.' })
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="start">
      <h1>Mahjong</h1>

      <div className="field">
        <label htmlFor="nickname">Smeknamn</label>
        <input
          id="nickname"
          ref={nicknameRef}
          autoFocus
          maxLength={20}
          autoComplete="nickname"
          value={nickname}
          onChange={(e) => {
            setNickname(e.target.value)
            setErrors((prev) => ({ ...prev, nickname: undefined }))
          }}
          onKeyDown={(e) => e.key === 'Enter' && submit(code ? 'join' : 'create')}
          aria-invalid={!!errors.nickname}
          aria-describedby={errors.nickname ? 'nickname-error' : undefined}
        />
        {errors.nickname && <p id="nickname-error" className="error">{errors.nickname}</p>}
      </div>

      <div className="start-actions">
        <section className="card">
          <h2>Nytt spel</h2>
          <p className="muted">Skapa en lobby och dela koden med de andra.</p>
          <button className="primary" disabled={!!busy} onClick={() => submit('create')}>
            {busy === 'create' ? 'Skapar…' : 'Skapa nytt spel'}
          </button>
          {errors.create && <p role="alert" className="error">{errors.create}</p>}
        </section>

        <section className="card">
          <h2>Gå med i spel</h2>
          <div className="field">
            <label htmlFor="code">Lobbykod</label>
            <input
              id="code"
              ref={codeRef}
              className="mono code-input"
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              value={code}
              onChange={(e) => {
                setCode(e.target.value.toUpperCase().replace(/\s/g, '').slice(0, 6))
                setErrors((prev) => ({ ...prev, code: undefined }))
              }}
              onKeyDown={(e) => e.key === 'Enter' && submit('join')}
              aria-invalid={!!errors.code}
              aria-describedby={errors.code ? 'code-error' : undefined}
            />
            {errors.code && <p id="code-error" className="error">{errors.code}</p>}
          </div>
          <button className="secondary" disabled={!!busy} onClick={() => submit('join')}>
            {busy === 'join' ? 'Ansluter…' : 'Gå med'}
          </button>
          {errors.join && <p role="alert" className="error">{errors.join}</p>}
        </section>
      </div>
    </div>
  )
}
