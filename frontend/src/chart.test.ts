import { describe, expect, it } from 'vitest'

import { shortName, spreadLabels, xTicks, yScale, yTicks } from './chart.ts'

describe('shortName', () => {
  it('kortar namn över 12 tecken till 12 med …', () => {
    expect(shortName('Christoffer')).toBe('Christoffer')
    expect(shortName('Christofferson')).toBe('Christoffer…')
    expect([...shortName('Christofferson')]).toHaveLength(12)
    expect(shortName('Åsa-Britt Öberg')).toBe('Åsa-Britt Ö…')
    expect(shortName('Wilhelmina Wikström')).toBe('Wilhelmina…') // inget mellanslag före …
    expect(shortName('Christoffer', 8)).toBe('Christo…')
    expect(shortName('Sigge', 8)).toBe('Sigge')
  })
})

describe('xTicks', () => {
  it('alla ronder när de är få', () => {
    expect(xTicks(1)).toEqual([0, 1])
    expect(xTicks(3)).toEqual([0, 1, 2, 3])
  })

  it('högst 11 tal och alltid den sista ronden', () => {
    const t = xTicks(30)
    expect(t.length).toBeLessThanOrEqual(11)
    expect(t[0]).toBe(0)
    expect(t.at(-1)).toBe(30)
    expect(xTicks(12)).toEqual([0, 2, 4, 6, 8, 10, 12])
  })
})

describe('yScale', () => {
  it('lägsta längst ner, högsta överst, 0 alltid med', () => {
    const y = yScale([-60, 120], 10, 110)
    expect(y(-60)).toBe(110)
    expect(y(120)).toBe(10)
    expect(yScale([20, 40], 0, 100)(0)).toBe(100)
  })

  it('bara nollor (oavgjort) ger mitten, inte NaN', () => {
    expect(yScale([0, 0, 0], 10, 110)(0)).toBe(60)
  })
})

describe('yTicks', () => {
  it('lägsta, 0 och högsta', () => {
    const values = [0, -60, 120]
    expect(yTicks(values, yScale(values, 0, 300), 20).sort((a, b) => a - b)).toEqual([-60, 0, 120])
  })

  it('tar bort ett tal för nära 0', () => {
    const values = [0, -2, 120]
    expect(yTicks(values, yScale(values, 0, 300), 20).sort((a, b) => a - b)).toEqual([0, 120])
  })

  it('bara nollor ger bara 0', () => {
    expect(yTicks([0, 0], yScale([0, 0], 0, 300), 20)).toEqual([0])
  })
})

describe('spreadLabels', () => {
  it('lika värden hamnar minst gap isär i inmatad ordning', () => {
    const out = spreadLabels([100, 100, 100, 100], 20, 0, 300)
    expect(out).toEqual([...out].sort((a, b) => a - b))
    for (let i = 1; i < out.length; i++) expect(out[i] - out[i - 1]).toBeGreaterThanOrEqual(20)
  })

  it('behåller ordningen och rör inte etiketter som redan har plats', () => {
    expect(spreadLabels([50, 10, 200, 120], 20, 0, 300)).toEqual([50, 10, 200, 120])
    const out = spreadLabels([105, 100, 300, 0], 20, 0, 300)
    expect(out[1]).toBeLessThan(out[0])
    expect(out[0] - out[1]).toBeGreaterThanOrEqual(20)
  })

  it('håller sig inom min–max', () => {
    const out = spreadLabels([295, 300, 300, 5], 20, 10, 290)
    expect(Math.min(...out)).toBeGreaterThanOrEqual(10)
    expect(Math.max(...out)).toBeLessThanOrEqual(290)
    const sorted = [...out].sort((a, b) => a - b)
    for (let i = 1; i < sorted.length; i++) expect(sorted[i] - sorted[i - 1]).toBeGreaterThanOrEqual(20)
  })
})
