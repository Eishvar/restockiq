import { fmtShort } from './format'

/** Share the last observed value between both series so the forecast has an anchor. */
export function bridgeForecastHistory(
  history: { date: string; total: number }[],
  days: { date: string; total: number }[],
) {
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
