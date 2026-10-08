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

export type MahjongDoubling = 'only_majors' | 'one_suit' | 'two_dragons_pair'

// Samma regler som backend (_check i scoring.py, Beslut 7, 29, 30). null = tillåten, annars skälet.
export function mahjongBlocked(d: Draft): Record<MahjongDoubling, string | null> {
  const m = d.mahjong
  return {
    only_majors:
      d.chows > 0 || majors(d) !== d.sets.length
        ? 'Kräver att alla fyra grupper är 3tal/4tal i 1, 9, vind, drake (Baspoäng).'
        : m.one_suit
          ? 'Kan inte kombineras med En serie: en serie har bara två ytterbrickor.'
          : null,
    // Täcker bara drak- och vind-3tal som angetts i Allmänna dubblingar (Beslut 29).
    one_suit:
      d.dragon_sets + d.round_wind_sets + d.own_wind_sets > 0
        ? 'Kan inte kombineras med drak- eller vind-3tal (Allmänna dubblingar).'
        : m.only_majors
          ? 'Kan inte kombineras med Enbart 1or, 9or, drakar och vindar: en serie har bara två ytterbrickor.'
          : null,
    two_dragons_pair:
      d.dragon_sets < 2 || !d.scoring_pair
        ? 'Kräver minst 2 drak-3tal (Allmänna dubblingar) och ett poänggivande par (Baspoäng).'
        : null,
  }
}

// En ruta som kryssats men inte längre är tillåten, t.ex. efter en ändring i en tidigare vy.
export function mahjongError(d: Draft): string | null {
  const blocked = mahjongBlocked(d)
  const key = (Object.keys(blocked) as MahjongDoubling[]).find((k) => d.mahjong[k] && blocked[k])
  return key ? blocked[key] : null
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

// Ny rond eller omladdning: har jag redan lämnat in visas väntläget med serverns version, annars Vy 1.
export function restore(mine: Submission | undefined): { draft: Draft; step: 1 | 'waiting' } {
  return mine ? { draft: fromSubmission(mine), step: 'waiting' } : { draft: emptyDraft(), step: 1 }
}

// Har servern tagit emot just det jag skickade? Servern skickar tillbaka score_input som den kom.
export function sameSubmission(a: Submission, b: Submission): boolean {
  return JSON.stringify([a.draw, a.score_input]) === JSON.stringify([b.draw, b.score_input])
}
