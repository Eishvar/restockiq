import { fmtShort } from './format'

/** `bridge` draws a faint connector from the last sold day to the first forecast day; it is not a forecast. */
export function bridgeForecastHistory(
  history: { date: string; total: number }[],
  days: { date: string; total: number; is_today?: boolean }[],
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
    // Today is not a forecast: it is still in progress. Keep its slot on the axis but plot nothing.
    ...days.map((d) => {
      if (d.is_today) return { label: fmtShort(d.date) }
      const value = Math.round(d.total)
      const first = !days.some((o) => !o.is_today && o.date < d.date)
      return { label: fmtShort(d.date), forecast: value, ...(first && anchorIndex >= 0 ? { bridge: value } : {}) }
    }),
  ]
}
