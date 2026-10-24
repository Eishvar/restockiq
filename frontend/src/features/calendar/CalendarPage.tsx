import { useState } from 'react'
import { Badge, Button, Card, ConfirmModal, EmptyState, Modal, SegmentedControl, useToast } from '../../components/ui'
import { useMe } from '../auth/api'
import { inputCls } from '../inventory/QtyInput'
import { fmtDay, fmtDayYear } from '../planning/format'
import MonthGrid, { TYPE_STYLE, eventsOn } from './MonthGrid'
import RestrictedRoleSwitch from '../auth/RestrictedRoleSwitch'
import {
  useAddEvent,
  useCalendar,
  useDeleteEvent,
  useEditEvent,
  useRecompute,
  type CalendarEvent,
  type EventInput,
  type EventType,
} from './api'

const TYPE_LABEL: Record<EventType, string> = { period: 'Period', public_holiday: 'Public holiday', local_event: 'Local event' }
const TYPE_HINT: Record<EventType, string> = {
  period: 'A run of unusually busy or quiet days, such as school holidays or Ramadan.',
  public_holiday: 'A national or state holiday.',
  local_event: 'A nearby event that may affect sales, such as a fair or exam week.',
}
type Filter = 'all' | EventType

const range = (e: { start_date: string; end_date: string }) =>
  e.start_date === e.end_date ? fmtDay(e.start_date) : `${fmtDay(e.start_date)} – ${fmtDay(e.end_date)}`

function EventForm({
  event, labels, defaultDate, onClose,
}: { event: CalendarEvent | null; labels: string[]; defaultDate?: string; onClose: () => void }) {
  const add = useAddEvent()
  const edit = useEditEvent()
  const toast = useToast()
  const [type, setType] = useState<EventType>(event?.type ?? 'period')
  const [label, setLabel] = useState(event?.label ?? '')
  const [name, setName] = useState(event?.name ?? '')
  const [start, setStart] = useState(event?.start_date ?? defaultDate ?? '')
  const [end, setEnd] = useState(event?.end_date ?? defaultDate ?? '')
  const busy = add.isPending || edit.isPending
  const valid = name.trim() && start && end && end >= start && (type !== 'period' || label.trim())

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const body: EventInput = { type, label: type === 'period' ? label : null, name: name.trim(), start_date: start, end_date: end }
    try {
      if (event) await edit.mutateAsync({ id: event.id, ...body })
      else await add.mutateAsync(body)
      toast(event ? 'Calendar entry updated' : 'Added to your calendar. The next forecast will use it.', 'success')
      onClose()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not save', 'error')
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 text-sm">
      <label className="block">
        <span className="mb-1 block font-medium">What is it?</span>
        <select value={type} onChange={(e) => setType(e.target.value as EventType)} className={`${inputCls} w-full`}>
          {(Object.keys(TYPE_LABEL) as EventType[]).map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
        </select>
        <span className="mt-1 block text-xs text-slate-500">{TYPE_HINT[type]}</span>
      </label>
      {type === 'period' && (
        <label className="block">
          <span className="mb-1 block font-medium">Label</span>
          <input list="period-labels" value={label} onChange={(e) => setLabel(e.target.value)} className={`${inputCls} w-full`} placeholder="e.g. school_holidays" />
          <datalist id="period-labels">{labels.map((l) => <option key={l} value={l} />)}</datalist>
          <span className="mt-1 block text-xs text-slate-500">
            Reuse a label for similar periods, such as school_holidays each year.
          </span>
        </label>
      )}
      <label className="block">
        <span className="mb-1 block font-medium">Name</span>
        <input required value={name} onChange={(e) => setName(e.target.value)} className={`${inputCls} w-full`} placeholder="e.g. Year-end school holidays" />
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="mb-1 block font-medium">From</span>
          <input required type="date" value={start} onChange={(e) => { setStart(e.target.value); if (!end || end < e.target.value) setEnd(e.target.value) }} className={`${inputCls} w-full`} />
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">To</span>
          <input required type="date" min={start} value={end} onChange={(e) => setEnd(e.target.value)} className={`${inputCls} w-full`} />
        </label>
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
        <Button type="submit" disabled={!valid || busy}>{busy ? 'Saving…' : event ? 'Save' : 'Add'}</Button>
      </div>
    </form>
  )
}

export default function CalendarPage() {
  const me = useMe()
  const allowed = me.data?.role === 'owner' || me.data?.role === 'manager'
  const { data, isLoading, error } = useCalendar(!!allowed)
  const del = useDeleteEvent()
  const recompute = useRecompute()
  const toast = useToast()
  const [filter, setFilter] = useState<Filter>('all')
  const [form, setForm] = useState<{ open: boolean; event: CalendarEvent | null; date?: string }>({ open: false, event: null })
  const [view, setView] = useState<{ year: number; month: number } | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<CalendarEvent | null>(null)
  const [deleteError, setDeleteError] = useState('')

  if (me.isLoading) return <p className="text-sm text-slate-500">Loading…</p>
  if (!allowed)
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <h1 className="text-xl font-semibold">Calendar</h1>
        <EmptyState title="Only managers and the owner can change the calendar" hint="Switch to a permitted demo user to view and manage events." action={<RestrictedRoleSwitch permission="manager" />} />
      </div>
    )
  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>
  if (error || !data) return <EmptyState title="Could not load the calendar" hint={error?.message} />

  const shown = data.events.filter((e) => filter === 'all' || e.type === filter)
  const todayDate = new Date(`${data.today}T00:00:00`)
  const { year, month } = view ?? { year: todayDate.getFullYear(), month: todayDate.getMonth() }
  const day = selected ?? data.today
  const dayEvents = eventsOn(shown, day)
  const go = (delta: number) => {
    const d = new Date(year, month + delta, 1)
    setView({ year: d.getFullYear(), month: d.getMonth() })
  }
  const monthTitle = new Date(year, month, 1).toLocaleDateString('en-MY', { month: 'long', year: 'numeric' })
  const isCurrent = year === todayDate.getFullYear() && month === todayDate.getMonth()

  async function remove() {
    if (!deleteTarget) return
    setDeleteError('')
    try {
      await del.mutateAsync(deleteTarget.id)
      toast('Removed', 'success')
      setDeleteTarget(null)
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Could not delete')
    }
  }

  async function runRecompute() {
    try {
      await recompute.mutateAsync()
      toast('Forecast accuracy and safety buffers measured again', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not recompute', 'error')
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Calendar</h1>
          <p className="text-sm text-slate-600">School terms, holidays and events that may affect sales.</p>
        </div>
        <Button onClick={() => setForm({ open: true, event: null })}>+ Add to calendar</Button>
      </div>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="overflow-x-auto">
            <SegmentedControl<Filter>
              label="Show"
              value={filter}
              onChange={setFilter}
              options={[
                { value: 'all', label: 'All' },
                { value: 'period', label: 'Periods' },
                { value: 'public_holiday', label: 'Holidays' },
                { value: 'local_event', label: 'Events' },
              ]}
            />
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500">
            {data.buffers_updated_at ? `Buffers measured ${new Date(data.buffers_updated_at).toLocaleString('en-MY')}` : 'Buffers not measured yet'}
            <Button variant="secondary" onClick={runRecompute} disabled={recompute.isPending}>
              {recompute.isPending ? 'Measuring… (about 10 s)' : 'Recompute'}
            </Button>
          </div>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Calendar changes apply to the next plan. Recompute waits for the safety buffers to finish updating.
        </p>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-slate-900">{monthTitle}</h2>
          <div className="flex items-center gap-1">
            <Button variant="secondary" onClick={() => { setView(null); setSelected(data.today) }} disabled={isCurrent && day === data.today}>Today</Button>
            <Button variant="secondary" aria-label="Previous month" onClick={() => go(-1)}>‹</Button>
            <Button variant="secondary" aria-label="Next month" onClick={() => go(1)}>›</Button>
          </div>
        </div>

        <div className="mt-3">
          <MonthGrid
            year={year}
            month={month}
            today={data.today}
            events={shown}
            selected={day}
            onSelect={setSelected}
            onOpen={(e) => setForm({ open: true, event: e })}
          />
        </div>

        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
          {(Object.keys(TYPE_STYLE) as EventType[]).map((t) => (
            <span key={t} className="inline-flex items-center gap-1.5"><span className={`h-2.5 w-2.5 rounded-full ${TYPE_STYLE[t].dot}`} />{TYPE_STYLE[t].label}</span>
          ))}
        </div>

        <section aria-label="Selected day" className="mt-4 rounded-xl border border-slate-200 bg-brand-surface/50 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-900">{fmtDayYear(day)}{day === data.today && <span className="ml-2 text-xs font-medium text-brand-royal">Today</span>}</h3>
            <Button variant="secondary" onClick={() => setForm({ open: true, event: null, date: day })}>+ Add on this day</Button>
          </div>
          {dayEvents.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">Nothing on this day.</p>
          ) : (
            <ul className="mt-2 divide-y divide-slate-200">
              {dayEvents.map((e) => (
                <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-slate-900">{e.name}</span>
                      <Badge tone={e.type === 'period' ? 'good' : e.type === 'public_holiday' ? 'warn' : 'neutral'}>{TYPE_LABEL[e.type]}</Badge>
                      {e.source === 'manual' && <span className="text-xs text-slate-400">added by hand</span>}
                    </div>
                    <div className="text-xs text-slate-500">{range(e)}{e.type === 'period' && e.label ? ` · label: ${e.label}` : ''}</div>
                  </div>
                  <div className="whitespace-nowrap">
                    <Button variant="ghost" onClick={() => setForm({ open: true, event: e })}>Edit</Button>
                    <Button variant="ghost" onClick={() => { setDeleteTarget(e); setDeleteError('') }} disabled={del.isPending}>Delete</Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </Card>

      <Modal open={form.open} title={form.event ? 'Edit calendar entry' : 'Add to calendar'} onClose={() => setForm({ open: false, event: null })}>
        <EventForm key={form.event?.id ?? `new-${form.date ?? ''}`} event={form.event} defaultDate={form.date} labels={data.labels} onClose={() => setForm({ open: false, event: null })} />
      </Modal>
      <ConfirmModal open={!!deleteTarget} title="Delete calendar entry?" description={deleteTarget ? `Delete “${deleteTarget.name}” from the calendar? This cannot be undone.` : ''} pending={del.isPending} error={deleteError} onCancel={() => { setDeleteTarget(null); setDeleteError('') }} onConfirm={remove} />
    </div>
  )
}
