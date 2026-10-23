export type AccuracyValues = {
  wape_total: number
  baseline_naive_wape: number | null
  baseline_flat_wape: number | null
}

export const forecastAccuracyPercent = (wape: number) =>
  Number.isFinite(wape) ? Math.min(100, Math.max(0, 100 - Math.round(wape * 100))) : 0

export function compareFourWeekBaseline(forecastError: number, baselineError: number | null) {
  if (!Number.isFinite(forecastError) || baselineError === null || !Number.isFinite(baselineError)) return { text: 'No 4-week comparison available', reduction: null }
  const forecast = Math.max(0, forecastError)
  const baseline = Math.max(0, baselineError)
  if (baseline === 0) return forecast === 0
    ? { text: 'Matches the 4-week average', reduction: 0 }
    : { text: 'The 4-week average has lower error', reduction: null }
  const reduction = ((baseline - forecast) / baseline) * 100
  if (reduction > 0) return { text: `${Math.round(reduction)}% less error than a 4-week average`, reduction }
  if (reduction === 0) return { text: 'Matches the 4-week average', reduction }
  return { text: `${Math.round(Math.abs(reduction))}% more error than a 4-week average`, reduction }
}

export function accuracyBars(data: AccuracyValues) {
  const clean = (value: number) => Number.isFinite(value) ? Math.max(0, value) : 0
  const entries = [
    { label: 'RestockAI forecast', value: clean(data.wape_total), color: 'bg-emerald-600', highlight: true },
    ...(data.baseline_naive_wape !== null && Number.isFinite(data.baseline_naive_wape) ? [{ label: 'Same day last week', value: clean(data.baseline_naive_wape), color: 'bg-slate-300', highlight: false }] : []),
    ...(data.baseline_flat_wape !== null && Number.isFinite(data.baseline_flat_wape) ? [{ label: 'Average of the last 4 weeks', value: clean(data.baseline_flat_wape), color: 'bg-amber-400', highlight: false }] : []),
  ]
  const smallest = Math.min(...entries.map((entry) => entry.value))
  const max = Math.max(...entries.map((entry) => entry.value), 0)
  return entries.map((entry) => ({ ...entry, width: max > 0 ? Math.max(0, Math.min(100, entry.value / max * 100)) : 0, best: entry.highlight && entry.value === smallest }))
}
