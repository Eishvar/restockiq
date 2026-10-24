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
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="grid grid-cols-7 border-b border-slate-200 bg-brand-surface text-center text-[11px] font-semibold uppercase tracking-wide text-slate-600">
        {WEEKDAYS.map((w) => <div key={w} className="py-2">{w}</div>)}
      </div>
      <div className="grid grid-cols-7">
        {days.map((d) => {
          const list = eventsOn(events, d.iso).sort((a, b) => Number(a.type === 'period') - Number(b.type === 'period') || a.start_date.localeCompare(b.start_date))
          const isToday = d.iso === today
          const isSelected = d.iso === selected
          return (
            <div
              key={d.iso}
              role="button"
              tabIndex={0}
              aria-label={`${d.iso}${list.length ? `, ${list.length} entr${list.length === 1 ? 'y' : 'ies'}` : ''}`}
              aria-pressed={isSelected}
              onClick={() => onSelect(d.iso)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(d.iso) } }}
              className={`min-h-[3.75rem] cursor-pointer border-b border-r border-slate-100 p-1 text-left transition hover:bg-brand-surface/70 sm:min-h-[6.5rem] sm:p-1.5 ${d.column === 6 ? 'border-r-0' : ''} ${d.inMonth ? '' : 'bg-slate-50/70 text-slate-400'} ${isSelected ? 'outline outline-2 -outline-offset-2 outline-brand-royal' : ''}`}
            >
              <div className="flex justify-center sm:justify-start">
                <span className={`flex h-6 min-w-6 items-center justify-center rounded-full px-1 text-xs font-semibold ${isToday ? 'bg-brand-royal text-white' : d.inMonth ? 'text-slate-800' : ''}`}>{d.day}</span>
              </div>

              {/* Small screens: dots only; the selected day's entries are listed under the calendar. */}
              <div className="mt-1 flex flex-wrap justify-center gap-0.5 sm:hidden">
                {list.slice(0, 4).map((e) => <span key={e.id} className={`h-1.5 w-1.5 rounded-full ${TYPE_STYLE[e.type].dot}`} />)}
              </div>

              <div className="mt-1 hidden space-y-1 sm:block">
                {list.slice(0, MAX_CHIPS).map((e) => {
                  const showName = e.start_date === d.iso || d.column === 0 || d.day === 1
                  return (
                    <button
                      key={e.id}
                      type="button"
                      title={`${e.name} (${TYPE_STYLE[e.type].label})`}
                      onClick={(ev) => { ev.stopPropagation(); onSelect(d.iso); onOpen(e) }}
                      className={`block w-full truncate text-left text-[11px] font-medium ${showName ? 'h-5 rounded px-1.5 leading-5' : 'h-1.5 -mx-1.5 !w-[calc(100%+0.75rem)] rounded-none px-0'} ${TYPE_STYLE[e.type].chip} ${showName ? '' : TYPE_STYLE[e.type].dot} ${d.inMonth ? '' : 'opacity-60'}`}
                    >
                      {showName ? e.name : ''}
                    </button>
                  )
                })}
                {list.length > MAX_CHIPS && <div className="px-1 text-[11px] font-medium text-slate-500">+{list.length - MAX_CHIPS} more</div>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
