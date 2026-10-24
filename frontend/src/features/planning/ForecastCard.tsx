import { useState } from 'react'
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from 'recharts'
import { Button, Card, Chip } from '../../components/ui'
import type { Drivers, Plan } from './api'
import { fmtDay, num, prettyState, weekdayLong } from './format'
import { bridgeForecastHistory } from './forecast-data'

const signed = (factor: number) => `${factor >= 1 ? '+' : '−'}${Math.abs(Math.round((factor - 1) * 100))}%`

/** Why this day is busy or quiet, as small tags. */
export function driverChips(date: string, d: Drivers): { text: string; hint: string }[] {
  const chips = [{ text: weekdayLong(date), hint: `${weekdayLong(date)}s are ${d.weekday_factor >= 1 ? 'busier' : 'quieter'} than average (x${num(d.weekday_factor)})` }]
  if (d.state !== 'normal') chips.push({ text: prettyState(d.state), hint: 'A period you set in the Calendar that changes how busy you are' })
  d.names.forEach((n) => chips.push({ text: n, hint: 'Holiday or event from your Calendar' }))
  if (d.holiday_effect !== 1) chips.push({ text: `Holiday ${signed(d.holiday_effect)}`, hint: 'How holidays changed your sales in the past' })
  if (d.event_effect !== 1) chips.push({ text: `Event ${signed(d.event_effect)}`, hint: 'How local events changed your sales in the past' })
  if (d.cold_start) chips.push({ text: 'Rough estimate', hint: 'Not enough sales history yet, so this is a simple average' })
  return chips
}

/** Splits "Nasi Goreng 炒饭" into the English name and its Chinese name. */
const splitName = (name: string): [string, string] => {
  const i = name.search(/[\u3400-\u9fff]/)
  return i <= 0 ? [name, ''] : [name.slice(0, i).trim(), name.slice(i).trim()]
}

export default function ForecastCard({ plan, accuracy }: { plan: Plan; accuracy?: number | null }) {
  const [showAll, setShowAll] = useState(false)
  const { days, dishes, history } = plan.forecast
  const chart = bridgeForecastHistory(history, days)
  const shown = showAll ? dishes : dishes.slice(0, 12)

  return (
    <Card title="What we expect you to sell">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {days.map((d) => (
          <div key={d.date} className="rounded-lg border border-slate-200 p-3">
            <div className="text-xs font-medium uppercase text-slate-500">{d.is_today ? 'Today (so far)' : fmtDay(d.date)}</div>
            <div className="mt-1 text-2xl font-semibold">{num(Math.round(d.total), 0)}</div>
            <div className="text-xs text-slate-500">dishes</div>
            <div className="mt-2 flex flex-wrap gap-1">
              {driverChips(d.date, d.drivers).map((c) => (
                <span key={c.text} title={c.hint}>
                  <Chip>{c.text}</Chip>
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between gap-4">
        <h3 className="text-sm font-semibold text-slate-800">Sold vs forecast</h3>
        <div className="flex items-baseline gap-2 rounded-xl bg-brand-surface px-3 py-1.5" title="How close past forecasts were to actual sales on a typical day">
          <span className="text-xs text-slate-600">Forecast accuracy</span>
          <span aria-label={accuracy == null ? 'Accuracy unavailable' : 'Accuracy on a typical day'} className="text-2xl font-extrabold tracking-tight text-brand-navy">{accuracy == null ? '—' : `${accuracy}%`}</span>
        </div>
      </div>
      <div className="mt-2 h-56 w-full" aria-label="Dishes sold per day: last 4 weeks and forecast">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chart} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
            <defs>
              <linearGradient id="soldFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--brand-muted)" stopOpacity={0.25} />
                <stop offset="100%" stopColor="var(--brand-muted)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--brand-border)" strokeOpacity={0.7} />
            <XAxis dataKey="label" interval="preserveStartEnd" minTickGap={32} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} allowDecimals={false} />
            <ChartTooltip />
            <Legend iconType="circle" />
            <Area name="Sold (last 4 weeks)" dataKey="actual" type="monotone" stroke="var(--brand-muted)" strokeWidth={2.5} fill="url(#soldFill)" dot={false} connectNulls={false} />
            <Line dataKey="bridge" type="monotone" stroke="var(--brand-royal)" strokeOpacity={0.35} strokeWidth={2} strokeDasharray="2 4" dot={false} activeDot={false} legendType="none" tooltipType="none" isAnimationActive={false} connectNulls />
            <Line name="Forecast" dataKey="forecast" type="monotone" stroke="var(--brand-royal)" strokeWidth={2.5} strokeDasharray="6 4" dot={{ r: 3.5, fill: '#fff', stroke: 'var(--brand-royal)', strokeWidth: 2 }} activeDot={{ r: 5 }} connectNulls={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-800">Forecast for each dish</h3>
        <div>
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full min-w-[34rem] border-collapse text-sm">
              <thead>
                <tr className="bg-brand-surface text-slate-600">
                  <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">Dish</th>
                  {days.map((d) => {
                    const [weekday, ...rest] = fmtDay(d.date).split(' ')
                    return (
                      <th key={d.date} scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">
                        <span className="block text-xs uppercase tracking-wide">{d.is_today ? 'Today' : weekday}</span>
                        <span className="block text-[11px] font-normal text-slate-500">{rest.join(' ')}</span>
                      </th>
                    )
                  })}
                  <th scope="col" className="whitespace-nowrap bg-brand-royal/10 px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-brand-navy">Total</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((dish) => {
                  const [english, chinese] = splitName(dish.name)
                  return (
                    <tr key={dish.menu_item_id} className="border-t border-slate-100 odd:bg-white even:bg-slate-50/60">
                      <th scope="row" className="px-4 py-2.5 text-left font-medium text-slate-900">
                        {english}
                        {chinese && <span className="ml-2 text-xs font-normal text-slate-500">{chinese}</span>}
                      </th>
                      {dish.qty.map((q, i) => (
                        <td key={i} className="px-3 py-2.5 text-right tabular-nums text-slate-700">{num(q, 0)}</td>
                      ))}
                      <td className="bg-brand-royal/5 px-4 py-2.5 text-right text-base font-bold tabular-nums text-brand-navy">{num(dish.total, 0)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {dishes.length > 12 && (
            <Button variant="ghost" className="mt-2" onClick={() => setShowAll((v) => !v)}>
              {showAll ? 'Show fewer' : `Show all ${dishes.length} dishes`}
            </Button>
          )}
        </div>
      </div>
    </Card>
  )
}
