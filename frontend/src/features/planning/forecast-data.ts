import { fmtShort } from './format'

/** `bridge` draws a faint connector from the last sold day to the first forecast day; it is not a forecast. */
export function bridgeForecastHistory(
  history: { date: string; total: number }[],
  days: { date: string; total: number }[],
) {
  // Days after the last recorded sales have no data yet; showing them as 0 would draw a false drop.
  let end = history.length
  while (end > 0 && !(history[end - 1].total > 0)) end--
  history = history.slice(0, end)
  const anchorIndex = history.length - 1
  return [
    ...history.map((h, i) => ({
      label: fmtShort(h.date),
      actual: h.total,
      ...(i === anchorIndex ? { bridge: h.total } : {}),
    })),
    ...days.map((d, i) => ({
      label: fmtShort(d.date),
      forecast: Math.round(d.total),
      ...(i === 0 && anchorIndex >= 0 ? { bridge: Math.round(d.total) } : {}),
    })),
  ]
}
