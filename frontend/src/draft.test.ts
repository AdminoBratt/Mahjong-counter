import { describe, expect, it } from 'vitest'

import { emptyDraft, fromSubmission, groupsError, toSubmission, type Draft } from './draft.ts'

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
