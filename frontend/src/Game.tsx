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
  toSubmission,
  type Draft,
  type MahjongDoubling,
  type Outcome,
} from './draft.ts'
import { WINDS, WIND_NAME, type Session, type Wind } from './useLobby.ts'

type Step = 1 | 2 | 3 | 'confirm'

const OUTCOMES: [Outcome, string][] = [
  ['mahjong', 'Jag gjorde Mahjong'],
  ['other', 'Någon annan gjorde Mahjong'],
  ['draw', 'Oavgjort (muren tog slut)'],
]

// Antalet steg följer svaret på "Hur slutade ronden?". Vid oavgjort hoppas dubblingarna över.
const STEPS: Record<Outcome, Step[]> = { mahjong: [1, 2, 3, 'confirm'], other: [1, 2, 'confirm'], draw: [1, 'confirm'] }
const STEP_NAME: Record<Step, string> = {
  1: 'Baspoäng',
  2: 'Allmänna dubblingar',
  3: 'Mahjong-dubblingar',
  confirm: 'Bekräfta',
}

export default function Game() {
  const { code = '' } = useParams()
  const { nickname, players, gameStatus, currentRound } = useOutletContext<Session>()
  const me = players.find((p) => p.nickname.toLowerCase() === nickname.toLowerCase())
  const [draft, setDraft] = useState(emptyDraft)
  const [step, setStep] = useState<Step>(1)
  const [roundId, setRoundId] = useState<string | null>(null)

  // Ny rond eller första laddningen: fyll i från min inlämning om den finns, annars tomt.
  // Görs bara då, så att andras inlämningar inte skriver över det man håller på med.
  if (currentRound && me && currentRound.id !== roundId) {
    setRoundId(currentRound.id)
    const mine = currentRound.submissions[me.id]
    setDraft(mine ? fromSubmission(mine) : emptyDraft())
    setStep(1)
  }

  if (gameStatus === 'waiting') return <Navigate to={`/lobby/${code}`} replace />
  if (!currentRound || !me?.wind) return null

  const steps = draft.outcome ? STEPS[draft.outcome] : null
  const next = () => steps && setStep(steps[steps.indexOf(step) + 1])
  const back = () => steps && setStep(steps[steps.indexOf(step) - 1])

  return (
    <div className="game">
      <header>
        <p className="muted">
          Rond {currentRound.round_number} · Din vind: {WIND_NAME[me.wind]}
        </p>
        <h1>{STEP_NAME[step]}</h1>
        {steps && (
          <p className="muted">
            Steg {steps.indexOf(step) + 1} av {steps.length}
          </p>
        )}
      </header>

      {step === 1 ? (
        <BaseView draft={draft} setDraft={setDraft} wind={me.wind} onNext={next} />
      ) : step === 2 ? (
        <DoublingsView
          draft={draft}
          setDraft={setDraft}
          wind={me.wind}
          roundWind={currentRound.round_wind}
          onNext={next}
          onBack={back}
        />
      ) : step === 3 ? (
        <MahjongView draft={draft} setDraft={setDraft} wind={me.wind} onNext={next} onBack={back} />
      ) : (
        <>
          <p>Bekräftelsen byggs i steg 3.8.</p>
          <div className="actions">
            <button className="secondary" onClick={back}>Tillbaka</button>
          </div>
        </>
      )}

      {import.meta.env.DEV && (
        <details className="dev-preview" open>
          <summary>Skickas i 3.8 (syns bara i dev)</summary>
          <pre className="mono">
            {JSON.stringify({ type: 'submit_score', round_id: currentRound.id, ...toSubmission(draft) }, null, 2)}
          </pre>
        </details>
      )}
    </div>
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
                {(
                  [
                    ['from_wall', 'Från muren', m.robbed_kong],
                    ['only_possible_tile', 'Enda möjliga bricka', false],
                    ['loose_tile', 'Lös bricka', m.robbed_kong],
                    ['robbed_kong', 'Sprängt 4tal', m.from_wall || m.loose_tile],
                  ] as const
                ).map(([key, label, disabled]) => (
                  <label key={key} className="option">
                    <input
                      type="checkbox"
                      checked={m[key]}
                      disabled={disabled}
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
