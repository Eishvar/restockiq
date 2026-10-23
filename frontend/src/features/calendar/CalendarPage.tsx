import { useState } from 'react'
import { Badge, Button, Card, ConfirmModal, EmptyState, Modal, SegmentedControl, Table, useToast } from '../../components/ui'
import { useMe } from '../auth/api'
import { inputCls } from '../inventory/QtyInput'
import { fmtDay } from '../planning/format'
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
  period: 'A stretch of days that changes how busy you are, such as semester, break, school holidays or Ramadan.',
  public_holiday: 'A day the country or state is off.',
  local_event: 'Something nearby that changes your sales, such as a fair, orientation or an exam week.',
}
type Filter = 'all' | EventType

const range = (e: { start_date: string; end_date: string }) =>
  e.start_date === e.end_date ? fmtDay(e.start_date) : `${fmtDay(e.start_date)} – ${fmtDay(e.end_date)}`

function EventForm({
  event, labels, onClose,
}: { event: CalendarEvent | null; labels: string[]; onClose: () => void }) {
  const add = useAddEvent()
  const edit = useEditEvent()
  const toast = useToast()
  const [type, setType] = useState<EventType>(event?.type ?? 'period')
  const [label, setLabel] = useState(event?.label ?? '')
  const [name, setName] = useState(event?.name ?? '')
  const [start, setStart] = useState(event?.start_date ?? '')
  const [end, setEnd] = useState(event?.end_date ?? '')
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
            Days with the same label are treated alike. Reuse a label you already have so the forecast learns from past years.
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
  const [form, setForm] = useState<{ open: boolean; event: CalendarEvent | null }>({ open: false, event: null })
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

  const rows = data.events.filter((e) => filter === 'all' || e.type === filter)

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
          <p className="text-sm text-slate-600">
            Tell us about school terms, holidays and events. The forecast learns how each one affects your sales, so entries here make the next plan better.
          </p>
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
          Changes are used by the next plan straight away. Safety buffers are re-measured in the background after each change; press Recompute to wait for it.
        </p>

        <div className="mt-3">
          {rows.length === 0 ? (
            <EmptyState title="Nothing here yet" hint="Add a period, holiday or event." />
          ) : (
            <Table head={['When', 'What', 'Type', '']}>
              {rows.map((e) => {
                const upcoming = e.end_date >= data.today
                return (
                  <tr key={e.id} className={upcoming ? '' : 'text-slate-500'}>
                    <td className="whitespace-nowrap">{range(e)}</td>
                    <td>
                      <div className="font-medium">{e.name}</div>
                      {e.type === 'period' && e.label && <div className="text-xs text-slate-500">label: {e.label}</div>}
                    </td>
                    <td className="whitespace-nowrap">
                      <Badge tone={e.type === 'period' ? 'good' : e.type === 'public_holiday' ? 'warn' : 'neutral'}>{TYPE_LABEL[e.type]}</Badge>
                      {e.source === 'manual' &&<span className="ml-1 text-xs text-slate-400">added by hand</span>}
                    </td>
                    <td className="whitespace-nowrap text-right">
                      <Button variant="ghost" onClick={() => setForm({ open: true, event: e })}>Edit</Button>
                      <Button variant="ghost" onClick={() => { setDeleteTarget(e); setDeleteError('') }} disabled={del.isPending}>Delete</Button>
                    </td>
                  </tr>
                )
              })}
            </Table>
          )}
        </div>
      </Card>

      <Modal open={form.open} title={form.event ? 'Edit calendar entry' : 'Add to calendar'} onClose={() => setForm({ open: false, event: null })}>
        <EventForm key={form.event?.id ?? 'new'} event={form.event} labels={data.labels} onClose={() => setForm({ open: false, event: null })} />
      </Modal>
      <ConfirmModal open={!!deleteTarget} title="Delete calendar entry?" description={deleteTarget ? `Delete “${deleteTarget.name}” from the calendar? This cannot be undone.` : ''} pending={del.isPending} error={deleteError} onCancel={() => { setDeleteTarget(null); setDeleteError('') }} onConfirm={remove} />
    </div>
  )
}
