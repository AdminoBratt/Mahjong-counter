import { describe, expect, it } from 'vitest'

import {
  bonusTiles,
  emptyDraft,
  fromSubmission,
  groupsError,
  honorsError,
  mahjongBlocked,
  mahjongError,
  restore,
  sameSubmission,
  toSubmission,
  type Draft,
} from './draft.ts'

const hand: Draft = {
  ...emptyDraft(),
  outcome: 'mahjong',
  chows: 2,
  sets: [
    { size: 3, concealed: true, major: false },
    { size: 4, concealed: false, major: true },
  ],
  scoring_pair: true,
  flowers: [3, 1],
  seasons: [2],
  mahjong: { ...emptyDraft().mahjong, from_wall: true },
}

describe('toSubmission', () => {
  it('maps every field of a mahjong hand', () => {
    expect(toSubmission(hand)).toEqual({
      draw: false,
      score_input: {
        chows: 2,
        sets: hand.sets,
        scoring_pair: true,
        flowers: [1, 3],
        seasons: [2],
        dragon_sets: 0,
        round_wind_sets: 0,
        own_wind_sets: 0,
        mahjong: { ...emptyDraft().mahjong, from_wall: true },
      },
    })
  })

  it('sends mahjong null when someone else won, even if bonuses were ticked earlier', () => {
    expect(toSubmission({ ...hand, outcome: 'other' }).score_input.mahjong).toBeNull()
  })

  it('sends an empty score_input on draw', () => {
    expect(toSubmission({ ...hand, outcome: 'draw' })).toEqual({ draw: true, score_input: {} })
  })
})

describe('fromSubmission', () => {
  it('round-trips a mahjong hand', () => {
    expect(fromSubmission(toSubmission(hand))).toEqual({ ...hand, flowers: [1, 3] })
  })

  it('round-trips a non-winning hand without losing fields', () => {
    const other = { ...hand, outcome: 'other' as const, mahjong: emptyDraft().mahjong }
    expect(fromSubmission(toSubmission(other))).toEqual({ ...other, flowers: [1, 3] })
  })

  it('restores a draw', () => {
    expect(fromSubmission({ draw: true, score_input: {} })).toEqual({ ...emptyDraft(), outcome: 'draw' })
  })

  it('fills in fields the server did not send', () => {
    expect(fromSubmission({ draw: false, score_input: { chows: 1 } })).toEqual({
      ...emptyDraft(),
      outcome: 'other',
      chows: 1,
    })
  })
})

describe('groupsError', () => {
  it('requires exactly four groups for mahjong', () => {
    expect(groupsError(hand)).toBeNull()
    expect(groupsError({ ...hand, chows: 1 })).toMatch('Du har 3')
  })

  it('ignores group count when not mahjong', () => {
    expect(groupsError({ ...hand, outcome: 'other', chows: 0 })).toBeNull()
  })
})

describe('honorsError', () => {
  const major = { size: 3 as const, concealed: false, major: true }
  const one = { ...emptyDraft(), outcome: 'other' as const, sets: [major] }

  it('allows as many dragon/wind sets as major sets', () => {
    expect(honorsError({ ...one, dragon_sets: 1 }, false)).toBeNull()
    expect(honorsError({ ...one, sets: [major, major], dragon_sets: 1, own_wind_sets: 1 }, false)).toBeNull()
  })

  it('rejects more dragon/wind sets than major sets', () => {
    expect(honorsError({ ...one, dragon_sets: 1, own_wind_sets: 1 }, false)).toMatch('bara 1')
    expect(honorsError({ ...one, round_wind_sets: 1, own_wind_sets: 1 }, false)).toMatch('angett 2')
    expect(honorsError({ ...emptyDraft(), dragon_sets: 1 }, false)).toMatch('bara 0')
  })

  it('counts a set in round and own wind once when they are the same wind', () => {
    const both = { ...one, round_wind_sets: 1, own_wind_sets: 1 }
    expect(honorsError(both, true)).toBeNull()
    expect(honorsError({ ...both, dragon_sets: 1 }, true)).toMatch('angett 2')
  })
})

describe('mahjongBlocked', () => {
  const major = { size: 3 as const, concealed: false, major: true }
  const majorsOnly: Draft = { ...emptyDraft(), outcome: 'mahjong', sets: [major, major, major, major] }
  const withMahjong = (d: Draft, patch: Partial<Draft['mahjong']>) => ({ ...d, mahjong: { ...d.mahjong, ...patch } })

  it('allows only_majors only when all four groups are major sets', () => {
    expect(mahjongBlocked(majorsOnly).only_majors).toBeNull()
    expect(mahjongBlocked({ ...majorsOnly, sets: [major, major, major], chows: 1 }).only_majors).toMatch('alla fyra')
    expect(mahjongBlocked({ ...majorsOnly, sets: [major, major, major, { ...major, major: false }] }).only_majors).toMatch(
      'alla fyra',
    )
  })

  it('needs two dragon sets and a scoring pair for two_dragons_pair', () => {
    const dragons = { ...majorsOnly, dragon_sets: 2, scoring_pair: true }
    expect(mahjongBlocked(dragons).two_dragons_pair).toBeNull()
    expect(mahjongBlocked({ ...dragons, dragon_sets: 1 }).two_dragons_pair).toMatch('minst 2')
    expect(mahjongBlocked({ ...dragons, scoring_pair: false }).two_dragons_pair).toMatch('par')
  })

  it('blocks one_suit when dragon or wind sets are given', () => {
    expect(mahjongBlocked(hand).one_suit).toBeNull()
    expect(mahjongBlocked({ ...majorsOnly, dragon_sets: 1 }).one_suit).toMatch('drak- eller vind')
    expect(mahjongBlocked({ ...majorsOnly, round_wind_sets: 1 }).one_suit).toMatch('drak- eller vind')
    expect(mahjongBlocked({ ...majorsOnly, own_wind_sets: 1 }).one_suit).toMatch('drak- eller vind')
  })

  it('makes one_suit and only_majors exclude each other in both directions', () => {
    expect(mahjongBlocked(withMahjong(majorsOnly, { one_suit: true })).only_majors).toMatch('En serie')
    expect(mahjongBlocked(withMahjong(majorsOnly, { only_majors: true })).one_suit).toMatch('Enbart')
  })
})

describe('mahjongError', () => {
  it('ignores blocked boxes that are not ticked', () => {
    expect(mahjongError(hand)).toBeNull()
  })

  it('reports a ticked box that is no longer allowed', () => {
    expect(mahjongError({ ...hand, mahjong: { ...hand.mahjong, only_majors: true } })).toMatch('alla fyra')
    expect(mahjongError({ ...hand, mahjong: { ...hand.mahjong, two_dragons_pair: true } })).toMatch('minst 2')
  })
})

describe('bonusTiles', () => {
  it('finds own flower and season by wind number', () => {
    const d = { ...emptyDraft(), flowers: [2, 3], seasons: [1] }
    expect(bonusTiles(d, 'south')).toMatchObject({ own: 2, ownFlower: true, ownSeason: false })
    expect(bonusTiles(d, 'east')).toMatchObject({ own: 1, ownFlower: false, ownSeason: true })
  })

  it('needs all four of a kind, and all eight for both', () => {
    const four = [1, 2, 3, 4]
    expect(bonusTiles({ ...emptyDraft(), flowers: four, seasons: [1, 2, 3] }, 'north')).toMatchObject({
      allFlowers: true,
      allSeasons: false,
      allEight: false,
    })
    expect(bonusTiles({ ...emptyDraft(), flowers: four, seasons: four }, 'north')).toMatchObject({
      allFlowers: true,
      allSeasons: true,
      allEight: true,
    })
  })
})

// Som servern skickar tillbaka en inlämning i lobby_update: via JSON, med uträkningen tillagd.
const fromServer = (d: Draft) => ({
  ...JSON.parse(JSON.stringify(toSubmission(d))),
  base_points: 24,
  doublings: 1,
  final_points: 48,
})

describe('restore (omladdning mitt i en rond)', () => {
  it('shows the waiting view with my submitted mahjong hand', () => {
    const { draft, step } = restore(fromServer(hand))
    expect(step).toBe('waiting')
    expect(draft).toEqual({ ...hand, flowers: [1, 3] })
  })

  it('restores a submitted draw', () => {
    const { draft, step } = restore(fromServer({ ...hand, outcome: 'draw' }))
    expect(step).toBe('waiting')
    expect(draft.outcome).toBe('draw')
  })

  it('starts on view 1 with an empty draft when I have not submitted', () => {
    expect(restore(undefined)).toEqual({ draft: emptyDraft(), step: 1 })
  })
})

describe('sameSubmission', () => {
  it('matches what the server echoes back, ignoring the calculation', () => {
    expect(sameSubmission(fromServer(hand), toSubmission(hand))).toBe(true)
  })

  it('tells an older submission apart', () => {
    expect(sameSubmission(fromServer(hand), toSubmission({ ...hand, chows: 1 }))).toBe(false)
  })
})
