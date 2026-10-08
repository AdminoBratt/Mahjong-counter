// Formulärets utkast och mappningen till/från score_input (ScoreInput i backend/app/scoring.py).
// Ingen poängräkning här, bara form. Backend räknar allt.

import type { Wind } from './useLobby.ts'

export type SetInput = { size: 3 | 4; concealed: boolean; major: boolean }
export type Outcome = 'mahjong' | 'other' | 'draw'
export type MahjongInput = {
  from_wall: boolean
  only_possible_tile: boolean
  loose_tile: boolean
  robbed_kong: boolean
  only_majors: boolean
  one_suit: boolean
  two_dragons_pair: boolean
}
export type ScoreInput = {
  chows: number
  sets: SetInput[]
  scoring_pair: boolean
  flowers: number[]
  seasons: number[]
  dragon_sets: number
  round_wind_sets: number
  own_wind_sets: number
  mahjong: MahjongInput | null
}
export type Submission = { draw: boolean; score_input: Partial<ScoreInput> }

// Mahjong-fälten ligger kvar när man byter svar, så att de inte försvinner om man ångrar sig.
export type Draft = Omit<ScoreInput, 'mahjong'> & { outcome: Outcome | null; mahjong: MahjongInput }

const NO_MAHJONG: MahjongInput = {
  from_wall: false,
  only_possible_tile: false,
  loose_tile: false,
  robbed_kong: false,
  only_majors: false,
  one_suit: false,
  two_dragons_pair: false,
}

export function emptyDraft(): Draft {
  return {
    outcome: null,
    chows: 0,
    sets: [],
    scoring_pair: false,
    flowers: [],
    seasons: [],
    dragon_sets: 0,
    round_wind_sets: 0,
    own_wind_sets: 0,
    mahjong: { ...NO_MAHJONG },
  }
}

export function toSubmission(d: Draft): Submission {
  // Vid oavgjort ignoreras poängen ändå, så inget skickas.
  if (d.outcome === 'draw') return { draw: true, score_input: {} }
  const { outcome, mahjong, ...rest } = d
  return {
    draw: false,
    score_input: {
      ...rest,
      flowers: [...d.flowers].sort((a, b) => a - b),
      seasons: [...d.seasons].sort((a, b) => a - b),
      mahjong: outcome === 'mahjong' ? mahjong : null,
    },
  }
}

export function fromSubmission({ draw, score_input: s }: Submission): Draft {
  return {
    ...emptyDraft(),
    ...s,
    outcome: draw ? 'draw' : s.mahjong ? 'mahjong' : 'other',
    mahjong: { ...NO_MAHJONG, ...s.mahjong },
  }
}

export function groups(d: Draft): number {
  return d.chows + d.sets.length
}

// Samma regel som backend (Beslut 10), så att felet syns innan något skickas.
export function groupsError(d: Draft): string | null {
  if (d.outcome === 'mahjong' && groups(d) !== 4) {
    return `Mahjong kräver exakt fyra grupper (3-följder + 3tal/4tal). Du har ${groups(d)}.`
  }
  return null
}

export function majors(d: Draft): number {
  return d.sets.filter((s) => s.major).length
}

// Samma regel som backend (_check i scoring.py): drak- och vind-3tal måste vara 3tal i 1, 9, vind, drake.
// Är egen vind också rondens vind är det samma 3tal, så det räknas en gång.
export function honorsError(d: Draft, sameWind: boolean): string | null {
  const used = d.dragon_sets + (sameWind ? d.round_wind_sets : d.round_wind_sets + d.own_wind_sets)
  if (used > majors(d)) {
    return `Du har angett ${used} 3tal/4tal i drake eller vind, men bara ${majors(d)} 3tal/4tal i 1, 9, vind, drake i Baspoäng.`
  }
  return null
}

const WIND_NUMBER: Record<Wind, number> = { east: 1, south: 2, west: 3, north: 4 }

// Fakta om blommor och årstider att visa i Vy 2. Inga dubblingar räknas här, det gör backend.
export function bonusTiles(d: Draft, wind: Wind) {
  const own = WIND_NUMBER[wind]
  const allFlowers = d.flowers.length === 4
  const allSeasons = d.seasons.length === 4
  return {
    own,
    ownFlower: d.flowers.includes(own),
    ownSeason: d.seasons.includes(own),
    allFlowers,
    allSeasons,
    allEight: allFlowers && allSeasons,
  }
}
