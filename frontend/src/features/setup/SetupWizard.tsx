import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Badge, Button, Card, EmptyState, useToast } from '../../components/ui'
import { useMe } from '../auth/api'
import { useAddEvent } from '../calendar/api'
import HelpChat from '../help/HelpChat'
import { useInventory } from '../inventory/api'
import OnboardingWizard from '../inventory/OnboardingWizard'
import { inputCls } from '../inventory/QtyInput'
import { useConnectPos } from '../pos/api'
import { useChooseCountry, useCompleteSetup, useSetupStatus, type SetupStep } from './api'

const STEPS: { key: SetupStep; label: string; optional?: boolean }[] = [
  { key: 'country', label: 'Country' },
  { key: 'pos', label: 'Sales system' },
  { key: 'inventory', label: 'Your stock' },
  { key: 'calendar', label: 'Calendar', optional: true },
]

function Stepper({ current }: { current: SetupStep }) {
  const at = STEPS.findIndex((s) => s.key === current)
  return (
    <ol className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
      {STEPS.map((s, i) => {
        const done = i < at
        const active = i === at
        return (
          <li key={s.key} className="flex items-center gap-2" aria-current={active ? 'step' : undefined}>
            <span
              className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
                done ? 'bg-emerald-600 text-white' : active ? 'border-2 border-brand-royal text-brand-royal' : 'border border-slate-300 text-slate-400'
              }`}
            >
              {done ? '✓' : i + 1}
            </span>
            <span className={active ? 'font-medium' : done ? 'text-slate-700' : 'text-slate-400'}>
              {s.label}
              {s.optional && <span className="ml-1 text-xs text-slate-400">(optional)</span>}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

// ---------- Step 1 ----------
function CountryStep() {
  const choose = useChooseCountry()
  const toast = useToast()
  const [picked, setPicked] = useState('MY')

  async function next() {
    try {
      const r = await choose.mutateAsync(picked)
      toast(
        `Currency set to ${r.status.currency}. Added ${r.holidays_added} public holiday${r.holidays_added === 1 ? '' : 's'}` +
          (r.holidays_already_there ? ` (${r.holidays_already_there} were already on your calendar).` : '.'),
        'success',
      )
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not save', 'error')
    }
  }

  return (
    <Card title="Where is your business?">
      <p className="text-sm text-slate-600">
        We use this to show prices in the right currency and to add your country&apos;s public holidays to the calendar, because holidays change how many customers you get.
      </p>
      <div className="mt-4 space-y-2">
        <label className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 ${picked === 'MY' ? 'border-brand-royal bg-brand-surface' : 'border-slate-200'}`}>
          <input type="radio" name="country" checked={picked === 'MY'} onChange={() => setPicked('MY')} className="mt-1" />
          <span>
            <span className="font-medium">Malaysia</span>
            <span className="block text-xs text-slate-600">Prices in MYR (RM). Malaysian public holidays are added to your calendar.</span>
          </span>
        </label>
        <div className="flex items-center gap-3 rounded-lg border border-dashed border-slate-200 p-3 text-sm text-slate-400">
          <input type="radio" disabled className="mt-0.5" />
          <span>Other countries <Badge>coming soon</Badge></span>
        </div>
      </div>
      <div className="mt-4 flex justify-end">
        <Button onClick={next} disabled={choose.isPending}>{choose.isPending ? 'Saving…' : 'Continue'}</Button>
      </div>
    </Card>
  )
}

// ---------- Step 2 ----------
function PosStep() {
  const connect = useConnectPos()
  const toast = useToast()
  const [understood, setUnderstood] = useState(false)

  async function next() {
    try {
      await connect.mutateAsync('feedme')
      toast('FeedMe connected', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not connect', 'error')
    }
  }

  return (
    <Card title="Connect your sales system (POS)">
      <p className="text-sm text-slate-600">
        RestockAI learns from what you sell. Pick the system your till uses.
      </p>
      <div className="mt-3 space-y-2">
        <div className="flex items-start gap-3 rounded-lg border border-brand-royal bg-brand-surface p-3">
          <input type="radio" checked readOnly className="mt-1" />
          <span>
            <span className="font-medium">FeedMe POS</span> <Badge tone="warn">demo: simulated</Badge>
            <span className="block text-xs text-slate-600">In this demo FeedMe is a stand-in screen with made-up sales. No real FeedMe account is used.</span>
          </span>
        </div>
        <div className="flex items-center gap-3 rounded-lg border border-dashed border-slate-200 p-3 text-sm text-slate-400">
          <input type="radio" disabled />
          <span>Other POS systems <Badge>coming soon</Badge></span>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        <p className="font-medium">You will export your sales from FeedMe</p>
        <p className="mt-1">
          RestockAI does not read your till by itself yet. Each day (or each week), export your daily sales from FeedMe as a CSV file and upload it here.
          It takes about a minute, and automatic syncing is planned for later.
        </p>
        <p className="mt-2">
          Want to see what that looks like?{' '}
          <Link to="/pos/feedme" className="font-medium underline" target="_blank" rel="noreferrer">Open the simulated FeedMe screen</Link>.
        </p>
      </div>

      <label className="mt-4 flex items-start gap-2 text-sm">
        <input type="checkbox" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} className="mt-1" />
        <span>I understand I need to export my sales from FeedMe and upload them to RestockAI.</span>
      </label>
      <div className="mt-4 flex justify-end">
        <Button onClick={next} disabled={!understood || connect.isPending}>{connect.isPending ? 'Connecting…' : 'Connect FeedMe'}</Button>
      </div>
    </Card>
  )
}

// ---------- Step 3 ----------
function InventoryStep() {
  const { data, isLoading, error } = useInventory()
  if (isLoading) return <p className="text-sm text-slate-500">Loading your stock…</p>
  if (error || !data) return <EmptyState title="Could not load your stock" hint={error?.message} />
  return <OnboardingWizard data={data} />
}

// ---------- Step 4 ----------
const KINDS = {
  busy: { label: 'Busy period', hint: 'More customers than usual, e.g. school holidays or a festival week.' },
  slow: { label: 'Slow period', hint: 'Fewer customers than usual, e.g. exam week or the fasting month.' },
}

function CalendarStep() {
  const add = useAddEvent()
  const complete = useCompleteSetup()
  const navigate = useNavigate()
  const toast = useToast()
  const [kind, setKind] = useState<keyof typeof KINDS>('busy')
  const [name, setName] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [added, setAdded] = useState<string[]>([])

  async function addPeriod(e: React.FormEvent) {
    e.preventDefault()
    try {
      await add.mutateAsync({ type: 'period', label: `${kind}_period`, name: name.trim(), start_date: start, end_date: end })
      setAdded((a) => [...a, `${KINDS[kind].label}: ${name.trim()} (${start} to ${end})`])
      setName('')
      setStart('')
      setEnd('')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not save', 'error')
    }
  }

  async function finish(skip: boolean) {
    try {
      await complete.mutateAsync(skip)
      toast('Setup finished. You can now plan purchases.', 'success')
      navigate('/plan', { replace: true })
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not finish', 'error')
    }
  }

  return (
    <Card title="Mark your busy and slow times (optional)">
      <p className="text-sm text-slate-600">
        Tell us when you expect to be busier or quieter than usual. You can skip this and add them later on the Calendar page.
        The forecast learns from how your sales behaved in similar periods, so a period that repeats helps more each time.
      </p>

      <form onSubmit={addPeriod} className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Type</span>
          <select value={kind} onChange={(e) => setKind(e.target.value as keyof typeof KINDS)} className={`${inputCls} w-full`}>
            {(Object.keys(KINDS) as (keyof typeof KINDS)[]).map((k) => <option key={k} value={k}>{KINDS[k].label}</option>)}
          </select>
          <span className="mt-1 block text-xs text-slate-500">{KINDS[kind].hint}</span>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Name</span>
          <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Year-end school holidays" className={`${inputCls} w-full`} />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">From</span>
          <input required type="date" value={start} onChange={(e) => { setStart(e.target.value); if (!end || end < e.target.value) setEnd(e.target.value) }} className={`${inputCls} w-full`} />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">To</span>
          <input required type="date" min={start} value={end} onChange={(e) => setEnd(e.target.value)} className={`${inputCls} w-full`} />
        </label>
        <div className="sm:col-span-2">
          <Button type="submit" variant="secondary" disabled={add.isPending || !name.trim() || !start || !end}>
            {add.isPending ? 'Adding…' : '+ Add this period'}
          </Button>
        </div>
      </form>

      {added.length > 0 && (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-700">
          {added.map((a) => <li key={a}>{a}</li>)}
        </ul>
      )}

      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <Button variant="secondary" onClick={() => finish(true)} disabled={complete.isPending}>Skip this step</Button>
        <Button onClick={() => finish(added.length === 0)} disabled={complete.isPending}>
          {complete.isPending ? 'Finishing…' : added.length ? 'Finish setup' : 'Finish without adding any'}
        </Button>
      </div>
    </Card>
  )
}

export default function SetupWizard() {
  const me = useMe()
  const { data, isLoading, error } = useSetupStatus()

  if (me.isLoading || isLoading) return <p className="p-6 text-sm text-slate-500">Loading…</p>
  if (error || !data) return <div className="p-6"><EmptyState title="Could not load the setup" hint={error?.message} /></div>
  if (me.data?.role !== 'owner') {
    return (
      <div className="mx-auto max-w-lg p-6">
        <EmptyState
          title="Only the owner can set up the business"
          hint="Sign out and choose Ah Hock (Owner)."
          action={<Link to="/login" className="text-sm font-medium text-brand-royal underline">Back to sign in</Link>}
        />
      </div>
    )
  }
  if (data.complete) return <Navigate to="/plan" replace />

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-4 py-3">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <span className="text-lg font-bold text-brand-royal">RestockAI</span>
          <span className="text-xs text-slate-500">First-time setup · {me.data?.name}</span>
        </div>
      </header>
      <main className="mx-auto max-w-5xl space-y-5 p-4 md:p-6">
        <div>
          <h1 className="text-xl font-semibold">Let&apos;s set up {me.data?.tenant_name}</h1>
          <p className="mt-1 text-sm text-slate-600">Four short steps. It takes a few minutes, and you only do it once.</p>
        </div>
        <Stepper current={data.step} />
        {data.step === 'country' && <CountryStep />}
        {data.step === 'pos' && <PosStep />}
        {data.step === 'inventory' && <InventoryStep />}
        {data.step === 'calendar' && <CalendarStep />}
      </main>
      <HelpChat />
    </div>
  )
}
