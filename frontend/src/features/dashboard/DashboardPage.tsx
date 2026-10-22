import { Link } from 'react-router-dom'
import { Badge, Card, EmptyState, Stat } from '../../components/ui'
import { fmtDay, num, rm } from '../planning/format'
import { useDashboard, type Dashboard } from './api'

const STATUS: Record<string, { label: string; tone: 'neutral' | 'good' | 'warn' | 'bad' }> = {
  draft: { label: 'Draft', tone: 'neutral' },
  pending_approval: { label: 'Waiting for approval', tone: 'warn' },
  approved: { label: 'Approved', tone: 'good' },
  sent: { label: 'Sent', tone: 'good' },
  received: { label: 'Received', tone: 'good' },
  rejected: { label: 'Rejected', tone: 'bad' },
}

const pct = (x: number) => `${Math.round(x * 100)}%`

function TimeSaved({ d }: { d: Dashboard }) {
  const days = d.hours_saved / 8
  return (
    <div className="rounded-xl bg-emerald-600 p-5 text-white shadow-sm">
      <div className="text-xs font-medium uppercase opacity-80">Time saved</div>
      {d.plans_completed === 0 ? (
        <>
          <div className="mt-1 text-3xl font-semibold">Not yet</div>
          <p className="mt-1 text-sm opacity-90">
            Planning by hand takes about {num(d.manual_hours_per_plan, 0)} hours. Approve your first plan and the time you saved shows here.
          </p>
        </>
      ) : (
        <>
          <div className="mt-1 text-4xl font-semibold">{num(d.hours_saved, 1)} hours</div>
          <p className="mt-1 text-sm opacity-90">
            about {num(days, 1)} working day{days === 1 ? '' : 's'} across {d.plans_completed} plan{d.plans_completed === 1 ? '' : 's'}
            {' '}(by hand: {num(d.manual_hours_per_plan, 0)} hours each, minus the minutes you spent checking).
          </p>
        </>
      )}
    </div>
  )
}

function Accuracy({ d }: { d: Dashboard }) {
  const a = d.accuracy
  if (!a) return <EmptyState title="Forecast accuracy is not measured yet" hint="It is worked out from your own sales history." />
  const bars = [
    { label: 'RestockIQ forecast', value: a.wape_total, color: 'bg-emerald-600' },
    ...(a.baseline_naive_wape !== null ? [{ label: "Same day last week", value: a.baseline_naive_wape, color: 'bg-slate-400' }] : []),
    ...(a.baseline_flat_wape !== null ? [{ label: 'Average of the last 4 weeks', value: a.baseline_flat_wape, color: 'bg-slate-400' }] : []),
  ]
  const top = Math.max(...bars.map((b) => b.value))
  return (
    <>
      <p className="text-sm text-slate-700">
        Our forecast is off by about <strong>{pct(a.wape_total)}</strong> on a typical day
        {a.baseline_flat_wape !== null && <>; a simple 4-week average is off by about <strong>{pct(a.baseline_flat_wape)}</strong></>}.
      </p>
      <ul className="mt-3 space-y-2">
        {bars.map((b) => (
          <li key={b.label} className="text-sm">
            <div className="flex justify-between"><span>{b.label}</span><span className="font-medium">{pct(b.value)} off</span></div>
            <div className="mt-1 h-2 rounded-full bg-slate-100">
              <div className={`h-2 rounded-full ${b.color}`} style={{ width: `${(b.value / top) * 100}%` }} />
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-slate-500">Checked on your past sales, looking {a.horizon_days} days ahead. Lower is better.</p>
    </>
  )
}

export default function DashboardPage() {
  const { data: d, isLoading, error } = useDashboard()
  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>
  if (error || !d) return <EmptyState title="Could not load the dashboard" hint={error?.message} />
  const maxSpend = Math.max(...d.top_spend.map((s) => s.total_rm), 1)

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="text-sm text-slate-600">How RestockIQ is helping, as of {fmtDay(d.today)}.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="md:col-span-2"><TimeSaved d={d} /></div>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-1">
          <Stat label="Average check time" value={d.avg_review_minutes === null ? '—' : `${num(d.avg_review_minutes, 1)} min`} hint="From plan made to order approved" />
          <Stat label="Plans made" value={d.plans_total} hint={`${d.plans_completed} approved`} />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Forecast accuracy"><Accuracy d={d} /></Card>

        <Card title="Latest plan">
          {!d.last_plan ? (
            <EmptyState title="No plan yet" action={<Link to="/plan" className="text-sm font-medium text-emerald-700 underline">Make your first plan</Link>} />
          ) : (
            <>
              <p className="text-sm text-slate-600">
                Made in {num(d.last_plan.duration_ms / 1000, 1)} s for {d.last_plan.horizon_days} day{d.last_plan.horizon_days === 1 ? '' : 's'} ·{' '}
                <strong>{rm(d.last_plan.grand_total_rm)}</strong> in total
              </p>
              <ul className="mt-3 divide-y divide-slate-100">
                {d.orders.map((o) => (
                  <li key={o.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                    <span>{o.supplier_name}</span>
                    <span className="flex items-center gap-2"><span className="text-slate-600">{rm(o.total_rm)}</span><Badge tone={STATUS[o.status]?.tone}>{STATUS[o.status]?.label ?? o.status}</Badge></span>
                  </li>
                ))}
              </ul>
              <Link to="/plan" className="mt-2 inline-block text-sm font-medium text-emerald-700 underline">Open the plan</Link>
            </>
          )}
        </Card>

        <Card title="Stock health">
          <div className="grid grid-cols-3 gap-3 text-center">
            <Stat label="Fine" value={d.inventory.ok} />
            <Stat label="Use soon" value={d.inventory.expiring_soon} />
            <Stat label="Expired" value={d.inventory.expired} />
          </div>
          {d.inventory.expired > 0 && (
            <p className="mt-3 text-sm text-red-800">Expired: {d.inventory.expired_items.join(', ')}. <Link to="/inventory" className="underline">Discard them</Link></p>
          )}
          {d.inventory.expiring_soon > 0 && (
            <p className="mt-1 text-sm text-amber-800">Use soon: {d.inventory.expiring_items.map((i) => `${i.name} (${i.days_left}d)`).join(', ')}</p>
          )}
        </Card>

        <Card title="Where the money goes (latest plan)">
          {d.top_spend.length === 0 ? (
            <EmptyState title="Nothing to show yet" hint="The five biggest items of your latest plan appear here." />
          ) : (
            <ul className="space-y-2">
              {d.top_spend.map((s) => (
                <li key={s.name} className="text-sm">
                  <div className="flex justify-between"><span>{s.name}</span><span className="font-medium">{rm(s.total_rm)}</span></div>
                  <div className="mt-1 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-emerald-600" style={{ width: `${(s.total_rm / maxSpend) * 100}%` }} /></div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
