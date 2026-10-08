import { useState, type Dispatch, type SetStateAction } from 'react'
import { Navigate, useOutletContext, useParams } from 'react-router-dom'

import {
  bonusTiles,
  emptyDraft,
  fromSubmission,
  groups,
  groupsError,
  honorsError,
  mahjongBlocked,
  mahjongError,
  majors,
  restore,
  sameSubmission,
  toSubmission,
  type Draft,
  type MahjongDoubling,
  type MahjongInput,
  type Outcome,
  type Submission,
} from './draft.ts'
import {
  WINDS,
  WIND_NAME,
  type Conflict,
  type CurrentRound,
  type Player,
  type RoundSubmission,
  type Session,
  type Wind,
} from './useLobby.ts'

type Step = 1 | 2 | 3 | 'confirm' | 'waiting'

const OUTCOMES: [Outcome, string][] = [
  ['mahjong', 'Jag gjorde Mahjong'],
  ['other', 'Någon annan gjorde Mahjong'],
  ['draw', 'Oavgjort (muren tog slut)'],
]
const OUTCOME_NAME = Object.fromEntries(OUTCOMES) as Record<Outcome, string>

// Antalet steg följer svaret på "Hur slutade ronden?". Vid oavgjort hoppas dubblingarna över.
const STEPS: Record<Outcome, Step[]> = { mahjong: [1, 2, 3, 'confirm'], other: [1, 2, 'confirm'], draw: [1, 'confirm'] }
const STEP_NAME: Record<Step, string> = {
  1: 'Baspoäng',
  2: 'Allmänna dubblingar',
  3: 'Mahjong-dubblingar',
  confirm: 'Bekräfta',
  waiting: 'Inlämnat',
}

// Noll utan tecken, annars alltid + eller − (Beslut 37).
const signed = new Intl.NumberFormat('sv-SE', { signDisplay: 'exceptZero' }).format
const tone = (n: number) => (n > 0 ? 'positive' : n < 0 ? 'negative' : '')

export default function Game() {
  const { code = '' } = useParams()
  const { nickname, players, gameStatus, currentRound, actionError, status, send } = useOutletContext<Session>()
  const me = players.find((p) => p.nickname.toLowerCase() === nickname.toLowerCase())
  const [draft, setDraft] = useState(emptyDraft)
  const [step, setStep] = useState<Step>(1)
  const [roundId, setRoundId] = useState<string | null>(null)
  const [sent, setSent] = useState<Submission | null>(null) // väntar på svar från servern
  const [editing, setEditing] = useState(false) // ändrar en inlämning som redan gäller
  const [missedRound, setMissedRound] = useState<number | null>(null)
  const mine = me ? currentRound?.submissions[me.id] : undefined

  // Ny rond eller första laddningen: fyll i från min inlämning om den finns, annars tomt.
  // Görs bara då, så att andras inlämningar inte skriver över det man håller på med.
  if (currentRound && me && currentRound.id !== roundId) {
    if (roundId !== null && editing) setMissedRound(currentRound.round_number - 1)
    setRoundId(currentRound.id)
    const start = restore(mine)
    setDraft(start.draft)
    setStep(start.step)
    setSent(null)
    setEditing(false)
  }

  // "Skicka in" är avstängd tills servern svarat: min inlämning i lobby_update, eller ett fel.
  if (sent && (actionError || status !== 'open')) setSent(null)
  else if (sent && mine && sameSubmission(mine, sent)) {
    setSent(null)
    setEditing(false)
    setStep('waiting')
  }

  if (gameStatus === 'waiting') return <Navigate to={`/lobby/${code}`} replace />
  if (!currentRound || !me?.wind) return null

  const round = currentRound
  const steps = draft.outcome ? STEPS[draft.outcome] : null
  const next = () => steps && setStep(steps[steps.indexOf(step) + 1])
  const back = () => steps && setStep(steps[steps.indexOf(step) - 1])

  function submit() {
    const submission = toSubmission(draft)
    send({ type: 'submit_score', round_id: round.id, ...submission })
    setSent(submission)
    setMissedRound(null)
  }

  function edit() {
    if (mine) setDraft(fromSubmission(mine))
    setEditing(true)
    setStep(1)
  }

  return (
    <div className="game">
      <header>
        <p className="muted">
          Rond {round.round_number} · Din vind: {WIND_NAME[me.wind]}
        </p>
        <h1>{STEP_NAME[step]}</h1>
        {steps && step !== 'waiting' && (
          <p className="muted">
            Steg {steps.indexOf(step) + 1} av {steps.length}
          </p>
        )}
      </header>

      <Standings players={players} meId={me.id} />

      {missedRound !== null && (
        <p role="status" className="notice">
          Rond {missedRound} avslutades medan du ändrade. Din förra inlämning gällde.
        </p>
      )}

      {step === 1 ? (
        <BaseView draft={draft} setDraft={setDraft} wind={me.wind} onNext={next} />
      ) : step === 2 ? (
        <DoublingsView
          draft={draft}
          setDraft={setDraft}
          wind={me.wind}
          roundWind={round.round_wind}
          onNext={next}
          onBack={back}
        />
      ) : step === 3 ? (
        <MahjongView draft={draft} setDraft={setDraft} wind={me.wind} onNext={next} onBack={back} />
      ) : step === 'confirm' ? (
        <>
          <section className="card" aria-labelledby="summary-heading">
            <h2 id="summary-heading">Dina val</h2>
            <Summary draft={draft} wind={me.wind} />
          </section>
          <p className="muted">Poängen räknas ut av servern när du skickat in.</p>
          {editing && <p className="muted">Din förra inlämning gäller tills du skickar in igen.</p>}
          {/* wrong_round kan bara komma när ronden avslutats under en ändring, och täcks av raden ovan. */}
          {actionError && actionError.code !== 'wrong_round' && (
            <p role="alert" className="error">
              {ERROR_TEXT[actionError.code] ?? actionError.message}
            </p>
          )}
          <div className="actions">
            <button className="secondary" onClick={back} disabled={sent !== null}>
              Tillbaka
            </button>
            <button className="primary" onClick={submit} disabled={sent !== null || status !== 'open'}>
              {sent ? 'Skickar…' : 'Skicka in'}
            </button>
          </div>
        </>
      ) : (
        mine && <WaitingView mine={mine} wind={me.wind} round={round} players={players} meId={me.id} onEdit={edit} />
      )}
    </div>
  )
}

// invalid_score har ett eget meddelande från servern, t.ex. "Mahjong kräver exakt fyra grupper".
const ERROR_TEXT: Record<string, string> = {
  not_active: 'Spelet är inte igång.',
  invalid_message: 'Något gick fel när inmatningen skickades. Försök igen.',
}

// Ställningen. Totalerna kommer från servern.
function Standings({ players, meId }: { players: Player[]; meId: string }) {
  return (
    <ol className="standings" aria-label="Ställning">
      {players.map((p) => (
        <li key={p.id}>
          <span>
            {p.nickname}
            {p.id === meId && <span className="muted"> (du)</span>}
          </span>
          <span className="muted">{p.wind && WIND_NAME[p.wind]}</span>
          <span className={`mono ${tone(p.total_score)}`}>{signed(p.total_score)}</span>
        </li>
      ))}
    </ol>
  )
}

const CONFLICT_TEXT: Record<Conflict, (names: { mahjong: string; draw: string }) => string> = {
  no_mahjong: () =>
    'Alla fyra har lämnat in, men ingen har angett Mahjong. Om någon vann måste den ändra sin inmatning. Om muren tog slut måste alla välja Oavgjort.',
  multiple_mahjong: ({ mahjong }) =>
    `Fler än en har angett Mahjong: ${mahjong}. Bara en kan vinna, den som angett fel ändrar sin inmatning.`,
  draw_disagreement: ({ draw }) =>
    `Alla har inte valt Oavgjort. Valt oavgjort: ${draw}. Antingen väljer alla Oavgjort, eller så ändrar de som valt det till rätt resultat.`,
}

type WaitingProps = {
  mine: RoundSubmission
  wind: Wind
  round: CurrentRound
  players: Player[]
  meId: string
  onEdit: () => void
}

// Efter inlämning. Allt läses från servern, inte från utkastet. Andras poäng visas inte (Beslut 34).
function WaitingView({ mine, wind, round, players, meId, onEdit }: WaitingProps) {
  const submitted = players.filter((p) => round.submissions[p.id])
  const names = (pick: (s: RoundSubmission) => boolean) =>
    submitted
      .filter((p) => pick(round.submissions[p.id]))
      .map((p) => p.nickname)
      .join(', ')

  return (
    <>
      {round.conflict && (
        <div role="alert" className="card conflict">
          <h2>Ronden kan inte avslutas</h2>
          <p>
            {CONFLICT_TEXT[round.conflict]({
              mahjong: names((s) => !!s.score_input.mahjong),
              draw: names((s) => s.draw),
            })}
          </p>
        </div>
      )}

      <div className="score-grid">
        <section className="card" aria-labelledby="mine-heading">
          <h2 id="mine-heading">Din inlämning</h2>
          {mine.draw ? (
            <p>Oavgjort, inga poäng.</p>
          ) : (
            <dl className="calc">
              <div>
                <dt>Baspoäng</dt>
                <dd className="mono">{mine.base_points}</dd>
              </div>
              <div>
                <dt>Dubblingar</dt>
                <dd className="mono">{mine.doublings}</dd>
              </div>
              <div>
                <dt>Slutpoäng</dt>
                <dd className="mono">{mine.final_points}</dd>
              </div>
            </dl>
          )}
          <Summary draft={fromSubmission(mine)} wind={wind} />
        </section>

        <section className="card" aria-labelledby="players-heading">
          <h2 id="players-heading">Spelare</h2>
          <p role="status" aria-atomic="true">
            {submitted.length} av 4 har lämnat in.
          </p>
          <ul className="seats">
            {players.map((p) => (
              <li key={p.id} className="seat">
                <span>
                  {p.nickname}
                  {p.id === meId && <span className="muted"> (du)</span>}
                </span>
                <span className={round.submissions[p.id] ? 'online' : 'muted'}>
                  {round.submissions[p.id] ? 'Har lämnat in' : 'Väntar'}
                  {!p.connected && ' · frånkopplad'}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <div className="actions">
        <button className={round.conflict ? 'primary' : 'secondary'} onClick={onEdit}>
          Ändra min inmatning
        </button>
      </div>
      <p className="muted">Din inlämning gäller tills du skickar in igen.</p>
    </>
  )
}

// Valen i klartext. Inga poäng: dem räknar servern.
function Summary({ draft: d, wind }: { draft: Draft; wind: Wind }) {
  if (!d.outcome) return null
  const list = (items: string[]) => (items.length ? items.join(', ') : 'Inga')
  const tiles = (nums: number[]) =>
    list(
      [...nums]
        .sort((a, b) => a - b)
        .map((n) => `${n} ${WINDS[n - 1][1]}${WINDS[n - 1][0] === wind ? ' (egen)' : ''}`),
    )
  const rows: [string, string][] = [['Resultat', OUTCOME_NAME[d.outcome]]]
  if (d.outcome !== 'draw') {
    rows.push(
      ['3-följder', String(d.chows)],
      [
        '3tal/4tal',
        list(
          d.sets.map(
            (s) => `${s.size}tal ${s.concealed ? 'på hand' : 'på bordet'} (${s.major ? '1, 9, vind, drake' : '2–8'})`,
          ),
        ),
      ],
      ['Poänggivande par', yesNo(d.scoring_pair)],
      ['Blommor', tiles(d.flowers)],
      ['Årstider', tiles(d.seasons)],
      ['3tal/4tal i drakar', String(d.dragon_sets)],
      ['3tal/4tal i rondens vind', yesNo(d.round_wind_sets === 1)],
      ['3tal/4tal i egen vind', yesNo(d.own_wind_sets === 1)],
    )
  }
  if (d.outcome === 'mahjong') {
    const picked = (options: [keyof MahjongInput, string][]) =>
      list(options.filter(([k]) => d.mahjong[k]).map(([, label]) => label))
    rows.push(['Mahjong-bonusar', picked(MAHJONG_BONUSES)], ['Mahjong-dubblingar', picked(MAHJONG_DOUBLINGS)])
  }
  return (
    <dl className="summary">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  )
}

const yesNo = (b: boolean) => (b ? 'Ja' : 'Nej')

type ViewProps = {
  draft: Draft
  setDraft: Dispatch<SetStateAction<Draft>>
  wind: Wind
  onNext: () => void
}

// Vy 1. Bara rådata, inga poäng visas: backend räknar allt.
function BaseView({ draft, setDraft, wind, onNext }: ViewProps) {
  const update = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }))
  const updateMahjong = (patch: Partial<Draft['mahjong']>) =>
    setDraft((d) => ({ ...d, mahjong: { ...d.mahjong, ...patch } }))
  const updateSet = (i: number, patch: Partial<Draft['sets'][number]>) =>
    setDraft((d) => ({ ...d, sets: d.sets.map((s, j) => (j === i ? { ...s, ...patch } : s)) }))
  const toggle = (list: number[], n: number) => (list.includes(n) ? list.filter((x) => x !== n) : [...list, n])

  const { outcome, mahjong: m } = draft
  const maxChows = 4 - draft.sets.length
  const bonusDisabled = {
    from_wall: m.robbed_kong,
    only_possible_tile: false,
    loose_tile: m.robbed_kong,
    robbed_kong: m.from_wall || m.loose_tile,
  }
  const error = groupsError(draft)

  return (
    <>
      <fieldset className="options">
        <legend>Hur slutade ronden?</legend>
        {OUTCOMES.map(([value, label]) => (
          <label key={value} className="option">
            <input type="radio" name="outcome" checked={outcome === value} onChange={() => update({ outcome: value })} />
            {label}
          </label>
        ))}
      </fieldset>
      {!outcome && <p className="muted">Välj hur ronden slutade för att gå vidare.</p>}

      {outcome && outcome !== 'draw' && (
        <div className="score-grid">
          <section className="card" aria-labelledby="groups-heading">
            <h2 id="groups-heading">Grupper</h2>

            <div className="field">
              <label htmlFor="chows">Antal 3-följder</label>
              <input
                id="chows"
                type="number"
                className="count"
                min={0}
                max={maxChows}
                value={draft.chows}
                aria-describedby="chows-hint"
                onChange={(e) => update({ chows: Math.max(0, Math.min(maxChows, Math.floor(Number(e.target.value)) || 0)) })}
              />
              <p id="chows-hint" className="muted">Ger 0p men räknas som grupp. Högst {maxChows}.</p>
            </div>

            <ol className="sets">
              {draft.sets.map((s, i) => (
                <li key={i} className="set-row">
                  <span className="set-name">3tal/4tal {i + 1}</span>
                  <Choice<3 | 4>
                    legend="Storlek"
                    name={`set-${i}-size`}
                    value={s.size}
                    options={[[3, '3tal'], [4, '4tal']]}
                    onChange={(size) => updateSet(i, { size })}
                  />
                  <Choice
                    legend="Var"
                    name={`set-${i}-concealed`}
                    value={s.concealed}
                    options={[[false, 'På bordet'], [true, 'På hand']]}
                    onChange={(concealed) => updateSet(i, { concealed })}
                  />
                  <Choice
                    legend="Brickor"
                    name={`set-${i}-major`}
                    value={s.major}
                    options={[[false, '2–8'], [true, '1, 9, vind, drake']]}
                    onChange={(major) => updateSet(i, { major })}
                  />
                  <button
                    className="secondary"
                    aria-label={`Ta bort 3tal/4tal ${i + 1}`}
                    onClick={() => update({ sets: draft.sets.filter((_, j) => j !== i) })}
                  >
                    Ta bort
                  </button>
                </li>
              ))}
            </ol>

            <div className="field">
              <button
                className="secondary add-set"
                disabled={groups(draft) >= 4}
                aria-describedby="groups-status"
                onClick={() => update({ sets: [...draft.sets, { size: 3, concealed: false, major: false }] })}
              >
                Lägg till 3tal/4tal
              </button>
              <p id="groups-status" className="muted">{groups(draft)} av 4 grupper.</p>
              {error && <p className="error">{error}</p>}
            </div>

            <label className="option">
              <input
                type="checkbox"
                checked={draft.scoring_pair}
                onChange={(e) => update({ scoring_pair: e.target.checked })}
              />
              Par i drake, rondens vind eller egen vind
            </label>
          </section>

          <section className="card" aria-labelledby="bonus-heading">
            <h2 id="bonus-heading">Blommor och årstider</h2>
            {(['flowers', 'seasons'] as const).map((key) => (
              <fieldset key={key} className="options">
                <legend>{key === 'flowers' ? 'Blommor' : 'Årstider'}</legend>
                {WINDS.map(([w, name], i) => (
                  <label key={w} className="option">
                    <input
                      type="checkbox"
                      checked={draft[key].includes(i + 1)}
                      onChange={() => update({ [key]: toggle(draft[key], i + 1) })}
                    />
                    {i + 1} {name}
                    {w === wind && <span className="muted"> (din vind)</span>}
                  </label>
                ))}
              </fieldset>
            ))}
          </section>

          {outcome === 'mahjong' && (
            <section className="card" aria-labelledby="mahjong-heading">
              <h2 id="mahjong-heading">Mahjong-bonusar</h2>
              <fieldset className="options" aria-describedby="mahjong-hint">
                <legend>Vinnande bricka</legend>
                {MAHJONG_BONUSES.map(([key, label]) => (
                  <label key={key} className="option">
                    <input
                      type="checkbox"
                      checked={m[key]}
                      disabled={bonusDisabled[key]}
                      onChange={(e) => updateMahjong({ [key]: e.target.checked })}
                    />
                    {label}
                  </label>
                ))}
              </fieldset>
              <p id="mahjong-hint" className="muted">
                Sprängt 4tal kan inte kombineras med Från muren eller Lös bricka.
              </p>
            </section>
          )}
        </div>
      )}

      <div className="actions">
        <button className="primary" disabled={!outcome || error !== null} onClick={onNext}>
          Nästa
        </button>
      </div>
    </>
  )
}

// Vy 2. Vy 1 vet inte vilken bricka ett 3tal i 1, 9, vind, drake är, så inget föreslås.
// Taket är antalet sådana 3tal. Blommor och årstider visas bara, backend härleder dubblingarna.
function DoublingsView({
  draft,
  setDraft,
  wind,
  roundWind,
  onNext,
  onBack,
}: ViewProps & { roundWind: Wind; onBack: () => void }) {
  const update = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }))
  const sameWind = wind === roundWind
  const maxDragons = Math.min(3, majors(draft))
  const none = maxDragons === 0
  const error = honorsError(draft, sameWind)
  const tiles = bonusTiles(draft, wind)

  const windOptions: [string, boolean, (on: boolean) => Partial<Draft>][] = sameWind
    ? [
        [
          `3tal/4tal i ${WIND_NAME[wind]} (rondens och egen vind)`,
          draft.round_wind_sets === 1,
          (on) => ({ round_wind_sets: +on, own_wind_sets: +on }),
        ],
      ]
    : [
        [`3tal/4tal i rondens vind (${WIND_NAME[roundWind]})`, draft.round_wind_sets === 1, (on) => ({ round_wind_sets: +on })],
        [`3tal/4tal i egen vind (${WIND_NAME[wind]})`, draft.own_wind_sets === 1, (on) => ({ own_wind_sets: +on })],
      ]

  return (
    <>
      <div className="score-grid">
        <section className="card" aria-labelledby="honors-heading">
          <h2 id="honors-heading">Drakar och vindar</h2>
          <p id="honors-hint" className="muted">
            Bara 3tal/4tal i drakar, rondens vind och din egen vind ger dubbling.
            {sameWind && ' Din vind är också rondens vind, så kryssrutan räknas som båda.'}
            {none
              ? ' Du har inga 3tal/4tal i 1, 9, vind, drake i Baspoäng.'
              : ` Högst ${majors(draft)} totalt, lika många som dina 3tal/4tal i 1, 9, vind, drake.`}
          </p>

          <div className="field">
            <label htmlFor="dragon-sets">Antal 3tal/4tal i drakar (röd, grön eller vit)</label>
            <input
              id="dragon-sets"
              type="number"
              className="count"
              min={0}
              max={maxDragons}
              value={draft.dragon_sets}
              disabled={none && draft.dragon_sets === 0}
              aria-invalid={error !== null}
              aria-describedby="honors-hint honors-error"
              onChange={(e) =>
                update({ dragon_sets: Math.max(0, Math.min(maxDragons, Math.floor(Number(e.target.value)) || 0)) })
              }
            />
          </div>

          <fieldset className="options" aria-describedby="honors-hint honors-error">
            <legend>Vindar</legend>
            {windOptions.map(([label, checked, patch]) => (
              <label key={label} className="option">
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={none && !checked}
                  onChange={(e) => update(patch(e.target.checked))}
                />
                {label}
              </label>
            ))}
          </fieldset>
          {error && (
            <p id="honors-error" className="error">
              {error}
            </p>
          )}
        </section>

        <section className="card" aria-labelledby="tiles-heading">
          <h2 id="tiles-heading">Blommor och årstider</h2>
          <p>
            Egen blomma ({tiles.own} {WIND_NAME[wind]}): {yesNo(tiles.ownFlower)}
          </p>
          <p>
            Egen årstid ({tiles.own} {WIND_NAME[wind]}): {yesNo(tiles.ownSeason)}
          </p>
          <p>Alla 4 blommor: {yesNo(tiles.allFlowers)}</p>
          <p>Alla 4 årstider: {yesNo(tiles.allSeasons)}</p>
          <p>Alla 8: {yesNo(tiles.allEight)}</p>
          <p className="muted">Räknas från Baspoäng. Gå tillbaka dit för att ändra.</p>
        </section>
      </div>

      <div className="actions">
        <button className="secondary" onClick={onBack}>
          Tillbaka
        </button>
        <button className="primary" disabled={error !== null} onClick={onNext}>
          Nästa
        </button>
      </div>
    </>
  )
}

const MAHJONG_BONUSES: [Exclude<keyof MahjongInput, MahjongDoubling>, string][] = [
  ['from_wall', 'Från muren'],
  ['only_possible_tile', 'Enda möjliga bricka'],
  ['loose_tile', 'Lös bricka'],
  ['robbed_kong', 'Sprängt 4tal'],
]

const MAHJONG_DOUBLINGS: [MahjongDoubling, string][] = [
  ['only_majors', 'Enbart 1or, 9or, drakar och vindar'],
  ['one_suit', 'Hela handen (utom paret) från en och samma serie'],
  ['two_dragons_pair', '3tal/4tal i två drakar + par i den tredje'],
]

// Vy 3, bara för vinnaren. Dragning och "ingen följd" härleds från tidigare vyer och visas bara.
// En spärrad ruta som redan är ikryssad förblir klickbar så att den kan kryssas ur (Beslut 31).
function MahjongView({ draft, setDraft, onNext, onBack }: ViewProps & { onBack: () => void }) {
  const blocked = mahjongBlocked(draft)
  const error = mahjongError(draft)
  const m = draft.mahjong

  return (
    <>
      <div className="score-grid">
        <section className="card" aria-labelledby="mahjong-doublings-heading">
          <h2 id="mahjong-doublings-heading">Mahjong-dubblingar</h2>
          <fieldset className="options">
            <legend>Gäller din hand?</legend>
            {MAHJONG_DOUBLINGS.map(([key, label]) => {
              const reason = blocked[key]
              const stale = reason !== null && m[key]
              return (
                <div key={key} className="field">
                  <label className="option">
                    <input
                      type="checkbox"
                      checked={m[key]}
                      disabled={reason !== null && !m[key]}
                      aria-invalid={stale}
                      aria-describedby={reason ? `${key}-reason` : undefined}
                      onChange={(e) => setDraft((d) => ({ ...d, mahjong: { ...d.mahjong, [key]: e.target.checked } }))}
                    />
                    {label}
                  </label>
                  {reason && (
                    <p id={`${key}-reason`} className={stale ? 'error' : 'muted'}>
                      {reason}
                    </p>
                  )}
                </div>
              )
            })}
          </fieldset>
        </section>

        <section className="card" aria-labelledby="hand-heading">
          <h2 id="hand-heading">Din hand</h2>
          <p>Vann genom dragning från muren: {yesNo(m.from_wall || m.loose_tile)}</p>
          <p>Ingen följd i handen: {yesNo(draft.chows === 0)}</p>
          <p className="muted">Räknas från Baspoäng (lös bricka räknas också som dragning). Gå tillbaka dit för att ändra.</p>
        </section>
      </div>

      <div className="actions">
        <button className="secondary" onClick={onBack}>
          Tillbaka
        </button>
        <button className="primary" disabled={error !== null} onClick={onNext}>
          Nästa
        </button>
      </div>
    </>
  )
}

type ChoiceProps<T> = {
  legend: string
  name: string
  value: T
  options: [T, string][]
  onChange: (value: T) => void
}

// Ett radiopar med egen etikett, t.ex. "Var: På bordet / På hand".
function Choice<T>({ legend, name, value, options, onChange }: ChoiceProps<T>) {
  return (
    <fieldset className="choice">
      <legend>{legend}</legend>
      {options.map(([v, label]) => (
        <label key={label} className="option">
          <input type="radio" name={name} checked={value === v} onChange={() => onChange(v)} />
          {label}
        </label>
      ))}
    </fieldset>
  )
}
