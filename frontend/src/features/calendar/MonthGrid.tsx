import type { CalendarEvent, EventType } from './api'

export const TYPE_STYLE: Record<EventType, { chip: string; dot: string; label: string }> = {
  period: { chip: 'bg-emerald-100 text-emerald-900', dot: 'bg-emerald-500', label: 'Period' },
  public_holiday: { chip: 'bg-amber-100 text-amber-900', dot: 'bg-amber-500', label: 'Public holiday' },
  local_event: { chip: 'bg-sky-100 text-sky-900', dot: 'bg-sky-500', label: 'Local event' },
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MAX_CHIPS = 3

const pad = (n: number) => String(n).padStart(2, '0')
export const isoDate = (y: number, m: number, d: number) => `${y}-${pad(m + 1)}-${pad(d)}`

/** Every day shown for a month: whole weeks, starting on Sunday. */
function monthDays(year: number, month: number) {
  const first = new Date(year, month, 1)
  const start = new Date(year, month, 1 - first.getDay())
  const weeks = Math.ceil((first.getDay() + new Date(year, month + 1, 0).getDate()) / 7)
  return Array.from({ length: weeks * 7 }, (_, i) => {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
    return { iso: isoDate(d.getFullYear(), d.getMonth(), d.getDate()), day: d.getDate(), inMonth: d.getMonth() === month, column: i % 7 }
  })
}

export const eventsOn = (events: CalendarEvent[], iso: string) =>
  events.filter((e) => e.start_date <= iso && iso <= e.end_date)

type Day = ReturnType<typeof monthDays>[number]
type Segment = { event: CalendarEvent; c0: number; c1: number; left: boolean; right: boolean; lane: number }

/** Bars for one week row: an entry that spans several days is one continuous bar, like Google Calendar. */
function weekSegments(week: Day[], events: CalendarEvent[]): Segment[] {
  const first = week[0].iso
  const last = week[6].iso
  const raw = events
    .filter((e) => e.start_date <= last && e.end_date >= first)
    .map((event) => {
      const c0 = Math.max(0, week.findIndex((d) => d.iso >= event.start_date))
      const endIdx = week.map((d) => d.iso <= event.end_date).lastIndexOf(true)
      return { event, c0, c1: endIdx, left: event.start_date < first, right: event.end_date > last }
    })
    .sort((a, b) => (b.c1 - b.c0) - (a.c1 - a.c0) || a.c0 - b.c0 || a.event.id - b.event.id)
  const laneEnds: number[][] = []
  return raw.map((r) => {
    let lane = laneEnds.findIndex((used) => used.every((col) => col < r.c0 || col > r.c1) )
    // A lane is free when none of its columns fall inside this bar.
    if (lane === -1) { lane = laneEnds.length; laneEnds.push([]) }
    for (let c = r.c0; c <= r.c1; c++) laneEnds[lane].push(c)
    return { ...r, lane }
  })
}

const LANE_PX = 22

export default function MonthGrid({
  year, month, today, events, selected, onSelect, onOpen,
}: {
  year: number
  month: number
  today: string
  events: CalendarEvent[]
  selected: string
  onSelect: (iso: string) => void
  onOpen: (event: CalendarEvent) => void
}) {
  const days = monthDays(year, month)
  const weeks = Array.from({ length: days.length / 7 }, (_, i) => days.slice(i * 7, i * 7 + 7))
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="grid grid-cols-7 border-b border-slate-200 bg-brand-surface text-center text-[11px] font-semibold uppercase tracking-wide text-slate-600">
        {WEEKDAYS.map((w) => <div key={w} className="py-2">{w}</div>)}
      </div>
      {weeks.map((week) => {
        const segs = weekSegments(week, events)
        const visible = segs.filter((s) => s.lane < MAX_CHIPS)
        const hiddenOn = week.map((_, c) => segs.filter((s) => s.lane >= MAX_CHIPS && s.c0 <= c && c <= s.c1).length)
        const lanes = Math.min(MAX_CHIPS, segs.reduce((m, s) => Math.max(m, s.lane + 1), 0)) + (hiddenOn.some(Boolean) ? 1 : 0)
        const rowHeight = Math.max(104, 36 + lanes * LANE_PX)
        return (
          <div key={week[0].iso} className="relative border-b border-slate-100 last:border-b-0" style={{ ['--row' as string]: `${rowHeight}px` }}>
            <div className="grid grid-cols-7">
              {week.map((d) => {
                const count = eventsOn(events, d.iso)
                const isToday = d.iso === today
                const isSelected = d.iso === selected
                return (
                  <div
                    key={d.iso}
                    role="button"
                    tabIndex={0}
                    aria-label={`${d.iso}${count.length ? `, ${count.length} entr${count.length === 1 ? 'y' : 'ies'}` : ''}`}
                    aria-pressed={isSelected}
                    onClick={() => onSelect(d.iso)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(d.iso) } }}
                    className={`min-h-[3.75rem] cursor-pointer border-r border-slate-100 p-1 transition hover:bg-brand-surface/70 sm:min-h-[var(--row)] sm:p-1.5 ${d.column === 6 ? 'border-r-0' : ''} ${d.inMonth ? '' : 'bg-slate-50/70 text-slate-400'} ${isSelected ? 'outline outline-2 -outline-offset-2 outline-brand-royal' : ''}`}
                  >
                    <div className="flex justify-center sm:justify-start">
                      <span className={`flex h-6 min-w-6 items-center justify-center rounded-full px-1 text-xs font-semibold ${isToday ? 'bg-brand-royal text-white' : d.inMonth ? 'text-slate-800' : ''}`}>{d.day}</span>
                    </div>
                    {/* Small screens: dots only; the selected day's entries are listed under the calendar. */}
                    <div className="mt-1 flex flex-wrap justify-center gap-0.5 sm:hidden">
                      {count.slice(0, 4).map((e) => <span key={e.id} className={`h-1.5 w-1.5 rounded-full ${TYPE_STYLE[e.type].dot}`} />)}
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="pointer-events-none absolute inset-x-0 top-8 hidden grid-cols-7 gap-y-[2px] sm:grid" style={{ gridAutoRows: `${LANE_PX - 2}px` }}>
              {visible.map((s) => (
                <button
                  key={`${s.event.id}-${s.c0}`}
                  type="button"
                  title={`${s.event.name} (${TYPE_STYLE[s.event.type].label}) · ${s.event.start_date === s.event.end_date ? s.event.start_date : `${s.event.start_date} to ${s.event.end_date}`}`}
                  onClick={() => { onSelect(week[s.c0].iso); onOpen(s.event) }}
                  style={{ gridColumn: `${s.c0 + 1} / ${s.c1 + 2}`, gridRow: s.lane + 1 }}
                  className={`pointer-events-auto truncate px-2 text-left text-[11px] font-semibold leading-[18px] hover:brightness-95 ${TYPE_STYLE[s.event.type].chip} ${s.left ? 'rounded-l-none' : 'ml-1 rounded-l-md'} ${s.right ? 'rounded-r-none' : 'mr-1 rounded-r-md'}`}
                >
                  {s.left && s.c0 === 0 && <span aria-hidden="true" className="mr-1 opacity-60">‹</span>}
                  {s.event.name}
                </button>
              ))}
              {hiddenOn.map((n, c) => n > 0 && (
                <div key={`more-${c}`} className="px-2 text-[11px] font-medium leading-[18px] text-slate-500" style={{ gridColumn: c + 1, gridRow: MAX_CHIPS + 1 }}>+{n} more</div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
