import test from 'node:test'
import assert from 'node:assert/strict'
import { forecastAccuracyPercent, compareFourWeekBaseline, accuracyBars } from '../src/features/dashboard/accuracy.ts'
import { formatActivityDetails } from '../src/features/activity/format.ts'
import { bridgeForecastHistory } from '../src/features/planning/forecast-data.ts'

test('accuracy hero is calculated from actual WAPE and bounded', () => {
  assert.equal(forecastAccuracyPercent(.173), 83)
  assert.equal(forecastAccuracyPercent(0), 100)
  assert.equal(forecastAccuracyPercent(1.4), 0)
  assert.equal(forecastAccuracyPercent(-.1), 100)
  assert.equal(forecastAccuracyPercent(NaN), 0)
})

test('four-week comparison uses relative error reduction, not a fabricated accuracy gain', () => {
  assert.deepEqual(compareFourWeekBaseline(.1, .2), {
    text: '50% less error than a 4-week average', reduction: 50,
  })
  const worse = compareFourWeekBaseline(.3, .2)
  assert.equal(worse.text, '50% more error than a 4-week average')
  assert.ok(Math.abs(worse.reduction + 50) < 1e-9)
})

test('missing, equal and zero baselines do not divide by zero or claim a win', () => {
  assert.equal(compareFourWeekBaseline(.1, null).reduction, null)
  assert.equal(compareFourWeekBaseline(.1, Infinity).reduction, null)
  assert.equal(compareFourWeekBaseline(.2, .2).text, 'Matches the 4-week average')
  assert.equal(compareFourWeekBaseline(0, 0).reduction, 0)
  assert.equal(compareFourWeekBaseline(.1, 0).text, 'The 4-week average has lower error')
})

test('Best is shown only when RestockAI has the lowest error, including ties', () => {
  assert.equal(accuracyBars({ wape_total: .1, baseline_naive_wape: .3, baseline_flat_wape: .2 })[0].best, true)
  assert.equal(accuracyBars({ wape_total: .3, baseline_naive_wape: .1, baseline_flat_wape: .2 })[0].best, false)
  assert.equal(accuracyBars({ wape_total: .1, baseline_naive_wape: .1, baseline_flat_wape: .2 })[0].best, true)
})

test('zero-error bar widths stay finite and missing comparisons are omitted', () => {
  const bars = accuracyBars({ wape_total: 0, baseline_naive_wape: 0, baseline_flat_wape: null })
  assert.equal(bars.length, 2)
  assert.ok(bars.every((bar) => Number.isFinite(bar.width) && bar.width === 0))
  assert.ok(accuracyBars({ wape_total: .2, baseline_naive_wape: NaN, baseline_flat_wape: null }).length === 1)
})

test('forecast starts at the final observed point without changing history or forecasts', () => {
  const history = [{ date: '2026-10-20', total: 90 }, { date: '2026-10-21', total: 100 }]
  const days = [{ date: '2026-10-22', total: 123.4 }]
  const before = structuredClone({ history, days })
  const chart = bridgeForecastHistory(history, days)
  assert.equal(chart.length, 3)
  assert.deepEqual(chart[0], { label: '20 Oct', actual: 90 })
  assert.deepEqual(chart[1], { label: '21 Oct', actual: 100, forecast: 100 })
  assert.deepEqual(chart[2], { label: '22 Oct', forecast: 123 })
  assert.deepEqual({ history, days }, before)
})

test('forecast handles missing history, missing forecast, and a zero anchor', () => {
  assert.deepEqual(bridgeForecastHistory([], []), [])
  assert.deepEqual(bridgeForecastHistory([], [{ date: '2026-10-22', total: 12 }]), [{ label: '22 Oct', forecast: 12 }])
  // Days after the last recorded sales are empty, not zero sales.
  assert.deepEqual(bridgeForecastHistory([{ date: '2026-10-21', total: 0 }], []), [])
  const trimmed = bridgeForecastHistory([{ date: '2026-10-20', total: 90 }, { date: '2026-10-21', total: 0 }], [{ date: '2026-10-23', total: 50 }])
  assert.deepEqual(trimmed, [{ label: '20 Oct', actual: 90, forecast: 90 }, { label: '23 Oct', forecast: 50 }])
})

test('audit details use everyday labels and Yes/No instead of raw JSON', () => {
  assert.deepEqual(formatActivityDetails({
    horizon_days: 3, risk_profile: 'never_run_out', has_number: true, discarded: false,
  }, 'purchase_order', '7'), [
    'purchase order #7', '3 days ahead', 'stock setting: never run out', 'has number: Yes', 'discarded: No',
  ])
  assert.deepEqual(formatActivityDetails({ horizon_days: 1 }), ['1 day ahead'])
})

test('nested audit details and object arrays never render [object Object]', () => {
  const result = formatActivityDetails({
    before: { final_packs: 2, active: false },
    after: { final_packs: 3, active: true },
    items: [{ ingredient_name: 'Rice', final_packs: 3 }, { ingredient_name: 'Eggs', final_packs: 2 }],
    flags: [true, false],
  }).join(' | ')
  assert.match(result, /before: packs: 2; active: No/)
  assert.match(result, /after: packs: 3; active: Yes/)
  assert.match(result, /items: item: Rice; packs: 3, item: Eggs; packs: 2/)
  assert.match(result, /flags: Yes, No/)
  assert.doesNotMatch(result, /\[object Object\]|final_packs|ingredient_name|[{}]/)
})

test('empty audit data is safe and meaningful user punctuation is preserved', () => {
  assert.deepEqual(formatActivityDetails(null), [])
  assert.deepEqual(formatActivityDetails({ omitted: null, skipped: '', text: "Chef's rice" }), ["text: Chef's rice"])
  assert.deepEqual(formatActivityDetails({ items: [] }), ['items: None'])
})
