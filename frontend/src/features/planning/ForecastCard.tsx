import { useState } from 'react'
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from 'recharts'
import { Button, Card, Chip, Table } from '../../components/ui'
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

export default function ForecastCard({ plan }: { plan: Plan }) {
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

      <div className="mt-4 h-56 w-full" aria-label="Dishes sold per day: last 4 weeks and forecast">
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
            <Line name="Forecast" dataKey="forecast" type="monotone" stroke="var(--brand-royal)" strokeWidth={2.5} strokeDasharray="6 4" dot={{ r: 3.5, fill: '#fff', stroke: 'var(--brand-royal)', strokeWidth: 2 }} activeDot={{ r: 5 }} connectNulls={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-800">Forecast for each dish</h3>
        <div>
          <Table head={['Dish', ...days.map((d) => (d.is_today ? 'Today' : fmtDay(d.date))), 'Total']}>
            {shown.map((dish) => (
              <tr key={dish.menu_item_id}>
                <td className="font-medium">{dish.name}</td>
                {dish.qty.map((q, i) => (
                  <td key={i} className="tabular-nums">{num(q, 0)}</td>
                ))}
                <td className="font-medium tabular-nums">{num(dish.total, 0)}</td>
              </tr>
            ))}
          </Table>
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
