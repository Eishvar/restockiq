import { fmtShort } from './format'

/** Share the last observed value between both series so the forecast has an anchor. */
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
      ...(i === anchorIndex ? { forecast: h.total } : {}),
    })),
    ...days.map((d) => ({ label: fmtShort(d.date), forecast: Math.round(d.total) })),
  ]
}
