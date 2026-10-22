import type { Line } from './api'
import { effectiveSchedule, fmtDay, formatQty, num, rm } from './format'

/** The tooltip on the buffer %: where the number comes from, in plain words. */
export function bufferTooltip(line: Line): string {
  const e = line.explanation
  if (e.method === 'measured' && e.service_level !== null)
    return `Covers ${Math.round(e.service_level * 100)}% of past cases, based on ${num(e.n_samples, 0)} past forecast checks against your own sales.`
  return 'A standard 15% until we have enough of your sales history to measure it.'
}

/** "Why?" in short sentences: forecast, stock, buffer, what to buy, what is left. */
export function whySentences(line: Line): string[] {
  const e = line.explanation
  const uom = line.base_uom
  const qty = (n: number) => formatQty(n, uom)
  const out: string[] = []

  const ahead = e.daily_need.slice(1) // tomorrow onwards; today's use is handled with the stock
  const first = ahead[0]?.date
  const last = ahead[ahead.length - 1]?.date
  if (first) out.push(`Forecast for ${fmtDay(first)}${first !== last ? ` – ${fmtDay(last)}` : ''}: ${qty(line.need_base)}.`)

  const todayUse = e.daily_need[0]?.need_base ?? 0
  if (e.stock.qty_base <= 0) out.push('You have none in stock.')
  else if (e.stock.expired) out.push(`Your ${qty(e.stock.qty_base)} has expired, so none of it is counted.`)
  else {
    const until = e.stock.expires_on ? ` (good until ${fmtDay(e.stock.expires_on)})` : ''
    out.push(
      `You have ${qty(e.stock.qty_base)}${until}${todayUse > 0 ? `, and today's use (${qty(todayUse)}) comes off first` : ''}: ${qty(line.usable_stock_base)} usable.`,
    )
  }

  const basis = (t: { method: string; service_level: number | null }) =>
    t.method === 'measured' && t.service_level !== null
      ? `enough in ${Math.round(t.service_level * 100)}% of your past cases`
      : 'a standard amount until we learn your pattern'

  const schedule = effectiveSchedule(line.buy_schedule, line.suggested_packs, line.final_packs)
  if (e.trips.length === 1) {
    const t = e.trips[0]
    out.push(`Safety buffer +${num(t.buffer_pct, 1)}% (${basis(t)}) = ${qty(t.target_base)}.`)
  } else {
    e.trips.forEach((t) =>
      out.push(
        `${fmtDay(t.date)}: ${qty(t.window_need_base)} needed for ${t.window_days} day${t.window_days === 1 ? '' : 's'}, +${num(t.buffer_pct, 1)}% safety (${basis(t)}) = ${qty(t.target_base)}; ${qty(t.usable_base)} already usable.`,
      ),
    )
  }

  const buys = schedule.map((t) => `${t.packs} ${line.pack_uom} on ${fmtDay(t.date)}`).join(', ')
  out.push(`Buy ${buys || 'nothing'} = ${rm(line.line_total_rm)}.`)
  if (line.final_packs !== line.suggested_packs)
    out.push(`You changed this from ${line.suggested_packs} to ${line.final_packs} ${line.pack_uom}.`)
  if (line.leftover_base > 0) out.push(`${qty(line.leftover_base)} left over at the end of the plan.`)
  return out
}
