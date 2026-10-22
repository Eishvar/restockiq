// Display helpers. Quantities are stored in base units (g / ml / pcs) and shown the way people say them.
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const DAYS_LONG = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const at = (iso: string) => new Date(iso + 'T00:00')

/** "Fri 23 Oct" */
export const fmtDay = (iso: string) => {
  const d = at(iso)
  return `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`
}

/** "Thu 22 Oct 2026" */
export const fmtDayYear = (iso: string) => `${fmtDay(iso)} ${at(iso).getFullYear()}`

export const weekdayLong = (iso: string) => DAYS_LONG[at(iso).getDay()]

/** "23 Oct" for chart axes */
export const fmtShort = (iso: string) => `${at(iso).getDate()} ${MONTHS[at(iso).getMonth()]}`

/** 1800 -> "1,800"; 2.456 -> "2.46" */
export function num(n: number, decimals = 2): string {
  const text = n.toLocaleString('en-US', { maximumFractionDigits: decimals })
  return text === '-0' ? '0' : text
}

/** 2400 g -> "2.4 kg"; 850 g -> "850 g"; 1500 ml -> "1.5 L"; 38 pcs -> "38 pcs" */
export function formatQty(base: number, uom: string): string {
  if (uom === 'g') return Math.abs(base) >= 1000 ? `${num(base / 1000)} kg` : `${num(base, 1)} g`
  if (uom === 'ml') return Math.abs(base) >= 1000 ? `${num(base / 1000)} L` : `${num(base, 1)} ml`
  if (uom === 'pcs') return `${num(base, 1)} ${base === 1 ? 'pc' : 'pcs'}`
  return `${num(base)} ${uom}`
}

export const rm = (n: number) => `RM ${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export type Trip = { date: string; packs: number }

/** Spread an edited pack count over the planned trips (same rule as the server's WhatsApp text). */
export function effectiveSchedule(schedule: Trip[], suggested: number, final: number): Trip[] {
  const trips = schedule.map((t) => ({ date: t.date, packs: t.packs }))
  let delta = final - suggested
  if (delta > 0 && trips.length) trips[0].packs += delta
  else if (delta < 0) {
    for (let i = trips.length - 1; i >= 0 && delta < 0; i--) {
      const take = Math.min(trips[i].packs, -delta)
      trips[i].packs -= take
      delta += take
    }
  }
  return trips.filter((t) => t.packs > 0)
}

/** "enough" -> "Enough", "break+intake" -> "Break + intake" */
export const prettyState = (state: string) => {
  const text = state.split('+').join(' + ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}
