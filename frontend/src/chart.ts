// Placering i poängkurvan (bildpunkter). Inga poäng räknas här: talen kommer från score_history.

// Namn längre än 12 tecken kortas i kurvans etiketter. Hela namnet står i tabellen och i SVG:ns title.
export function shortName(name: string): string {
  const chars = [...name]
  return chars.length > 12 ? chars.slice(0, 11).join('').trimEnd() + '…' : name
}

// Vilka ronder som får ett tal på x-axeln: högst max + 1 stycken, alltid 0 och den sista.
export function xTicks(last: number, max = 10): number[] {
  const step = Math.ceil(last / max) || 1
  const ticks = []
  for (let i = 0; i < last; i += step) ticks.push(i)
  return [...ticks, last]
}

// Värde → y. 0 är alltid med. Är alla värden lika hamnar de i mitten.
export function yScale(values: number[], top: number, bottom: number): (v: number) => number {
  const lo = Math.min(0, ...values)
  const hi = Math.max(0, ...values)
  if (lo === hi) return () => (top + bottom) / 2
  return (v) => bottom - ((v - lo) / (hi - lo)) * (bottom - top)
}

// Talen på y-axeln: lägsta, 0 och högsta. Ett tal för nära 0 (i bildpunkter) tas bort så att texten inte krockar.
export function yTicks(values: number[], y: (v: number) => number, gap: number): number[] {
  const ends = [Math.min(...values), Math.max(...values)].filter((v) => Math.abs(y(v) - y(0)) >= gap)
  return [...new Set([...ends, 0])]
}

// Etiketternas y vid linjernas slut, minst gap isär och inom min–max. Ordningen behålls, lika värden i inmatad ordning.
export function spreadLabels(ys: number[], gap: number, min: number, max: number): number[] {
  const order = ys.map((_, i) => i).sort((a, b) => ys[a] - ys[b] || a - b)
  const out = [...ys]
  let prev = -Infinity
  for (const i of order) prev = out[i] = Math.max(out[i], prev + gap, min)
  let next = Infinity
  for (const i of order.reverse()) next = out[i] = Math.min(out[i], next - gap, max)
  return out
}
