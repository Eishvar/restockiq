import { useState } from 'react'
import { Button, Card, ConfirmModal, EmptyState, useToast } from '../../components/ui'
import { useMe } from '../auth/api'
import { inputCls } from '../inventory/QtyInput'
import { fmtDayYear } from '../planning/format'
import RestrictedRoleSwitch from '../auth/RestrictedRoleSwitch'
import {
  useResetDemo,
  useSaveSettings,
  useSettings,
  type RiskProfile,
  type Settings,
} from './api'

const PROFILES: { value: RiskProfile; title: string; text: string }[] = [
  { value: 'lean', title: 'Lean', text: 'Buy tighter and waste less. You may run short now and then.' },
  { value: 'balanced', title: 'Balanced', text: 'A sensible middle. Recommended for most kitchens.' },
  { value: 'never_run_out', title: 'Never run out', text: 'Buy a bigger cushion so you almost never run short. Some extra may be left over.' },
]

const pct = (x: number) => `${Math.round(x * 100)}%`

function Risk({ s }: { s: Settings }) {
  const save = useSaveSettings()
  const toast = useToast()
  const [choice, setChoice] = useState<RiskProfile>(s.risk_profile)
  const changed = choice !== s.risk_profile

  async function apply() {
    try {
      await save.mutateAsync({ risk_profile: choice })
      toast('Saved. Safety buffers were measured again for this setting.', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not save', 'error')
    }
  }

  return (
    <Card title="How careful should we be about running out?">
      <p className="mb-3 text-sm text-slate-600">
        On top of the forecast we add a safety buffer, measured from how wrong the forecast was for each of your items in the past.
        This setting decides how often that buffer should be enough.
      </p>
      <div className="grid gap-3 md:grid-cols-3" role="radiogroup" aria-label="Risk setting">
        {PROFILES.map((p) => (
          <button
            key={p.value}
            role="radio"
            aria-checked={choice === p.value}
            onClick={() => setChoice(p.value)}
            className={`rounded-lg border p-3 text-left text-sm transition ${choice === p.value ? 'border-brand-royal bg-brand-surface ring-1 ring-brand-royal' : 'border-slate-200 hover:bg-slate-50'}`}
          >
            <div className="font-semibold">{p.title}{p.value === s.risk_profile && <span className="ml-2 text-xs font-normal text-slate-500">(current)</span>}</div>
            <div className="mt-1 text-slate-600">{p.text}</div>
          </button>
        ))}
      </div>

      <table className="mt-4 w-full text-left text-sm">
        <caption className="mb-1 text-left text-xs text-slate-500">How often the buffer is enough, by how long the item keeps</caption>
        <thead className="text-xs uppercase text-slate-500">
          <tr><th className="py-1 font-medium">Setting</th><th className="font-medium">Fresh (under 7 days)</th><th className="font-medium">Medium (7-29 days)</th><th className="font-medium">Long life (30+ days)</th></tr>
        </thead>
        <tbody>
          {PROFILES.map((p) => (
            <tr key={p.value} className={choice === p.value ? 'font-semibold text-brand-navy' : 'text-slate-700'}>
              <td className="py-1">{p.title}</td>
              {s.service_levels[p.value].map((x, i) => <td key={i}>{pct(x)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-slate-500">
        Fresh items get a lower number because leftovers spoil. Long-life items get a higher one because leftovers keep.
        {s.buffers_updated_at && ` Buffers last measured ${new Date(s.buffers_updated_at).toLocaleString('en-MY')}.`}
      </p>
      <div className="mt-3 flex items-center gap-3">
        <Button onClick={apply} disabled={!changed || save.isPending}>{save.isPending ? 'Updating…' : 'Save'}</Button>
      </div>
    </Card>
  )
}

function Baseline({ s }: { s: Settings }) {
  const save = useSaveSettings()
  const toast = useToast()
  const [date, setDate] = useState(s.today_override ?? '')

  async function saveDate(value: string | null) {
    try {
      await save.mutateAsync({ today_override: value })
      setDate(value ?? '')
      toast(value ? `The app now treats ${fmtDayYear(value)} as today` : 'Back to the real date', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not save', 'error')
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Demo date">
        <p className="mb-2 text-sm text-slate-600">
          For demos: pretend it is another day. Today is <strong>{fmtDayYear(s.today)}</strong>{s.today_override ? ' (set by you)' : ''}.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputCls} aria-label="Demo date" />
          <Button onClick={() => saveDate(date)} disabled={!date || date === s.today_override || save.isPending}>Use this date</Button>
          {s.today_override && <Button variant="secondary" onClick={() => saveDate(null)} disabled={save.isPending}>Use the real date</Button>}
        </div>
      </Card>
    </div>
  )
}

function Reset() {
  const reset = useResetDemo()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')

  async function go() {
    try {
      await reset.mutateAsync()
      setOpen(false)
      toast('Demo data reset. Everything is back to the starting example.', 'success')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reset')
    }
  }

  return (
    <Card title="Reset demo data">
      <p className="mb-3 text-sm text-slate-600">
        Wipes plans, orders, stock changes and calendar edits, then loads the starting example again. Users are kept.
      </p>
      <Button variant="danger" onClick={() => { setOpen(true); setError('') }}>Reset demo data</Button>
      <ConfirmModal open={open} title="Reset all demo data?" description="This cannot be undone. Everything you added or changed will be replaced by the example data." pending={reset.isPending} error={error} onCancel={() => { setOpen(false); setError('') }} onConfirm={() => void go()} />
    </Card>
  )
}

export default function SettingsPage() {
  const me = useMe()
  const isOwner = me.data?.role === 'owner'
  const { data, isLoading, error } = useSettings(isOwner)

  if (me.isLoading) return <p className="text-sm text-slate-500">Loading…</p>
  if (!isOwner)
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <h1 className="text-xl font-semibold">Settings</h1>
        <EmptyState title="Only the owner can change settings" hint="Switch to the owner demo user to view and change configuration." action={<RestrictedRoleSwitch permission="owner" />} />
      </div>
    )
  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>
  if (error || !data) return <EmptyState title="Could not load the settings" hint={error?.message} />

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="text-sm text-slate-600">{data.tenant_name}. Every change is written to the Activity record.</p>
      </div>
      <Risk key={data.risk_profile} s={data} />
      <Baseline key={`${data.manual_planning_hours}-${data.today_override}`} s={data} />
      <Reset />
    </div>
  )
}
