import { Link } from 'react-router-dom'
import { Badge, Card, EmptyState, PageSkeleton, Stat } from '../../components/ui'
import { fmtDay, rm } from '../planning/format'
import { useDashboard, type Dashboard } from './api'
import { accuracyBars, compareFourWeekBaseline, forecastAccuracyPercent } from './accuracy'

const STATUS: Record<string, { label: string; tone: 'neutral' | 'good' | 'warn' | 'bad' }> = {
  draft: { label: 'Draft', tone: 'neutral' },
  pending_approval: { label: 'Waiting for approval', tone: 'warn' },
  approved: { label: 'Approved', tone: 'good' },
  sent: { label: 'Sent', tone: 'good' },
  received: { label: 'Received', tone: 'good' },
  rejected: { label: 'Rejected', tone: 'bad' },
}

const pct = (x: number) => `${Math.round(x * 100)}%`

function Accuracy({ d }: { d: Dashboard }) {
  const a = d.accuracy
  if (!a || !Number.isFinite(a.wape_total)) return <EmptyState title="Forecast accuracy is not measured yet" hint="It is worked out from your own sales history." />
  const bars = accuracyBars(a)
  const comparison = compareFourWeekBaseline(a.wape_total, a.baseline_flat_wape)
  return (
    <>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3 rounded-xl bg-brand-surface p-4">
        <div><div className="text-xs font-bold uppercase tracking-wider text-brand-navy">Accuracy on a typical day</div><div className="mt-1 text-4xl font-extrabold tracking-tight text-brand-navy">{forecastAccuracyPercent(a.wape_total)}%</div></div>
        <div className="max-w-52 rounded-lg bg-white/75 px-3 py-2 text-sm font-semibold text-brand-navy">{comparison.text}</div>
      </div>
      <p className="text-xs text-slate-500">Based on past sales: 100% minus forecast error. This is a guide, not a guarantee.</p>
      <p className="mt-4 text-xs font-bold uppercase tracking-wide text-slate-500">Forecast Error — Lower is better ↓</p>
      <ul className="mt-3 space-y-2">
        {bars.map((b) => (
          <li key={b.label} className="text-sm">
            <div className="flex items-center justify-between gap-2"><span className="flex items-center gap-2">{b.label}{b.best && <Badge tone="good">Best</Badge>}</span><span className="font-medium">{pct(b.value)} off</span></div>
            <div className="mt-1 h-2 rounded-full bg-slate-100">
              <div className={`h-2 rounded-full ${b.color}`} style={{ width: `${b.width}%` }} />
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-slate-500">Checked on your past sales, looking {a.horizon_days} days ahead. Lower is better.</p>
    </>
  )
}

export default function DashboardPage() {
  const { data: d, isLoading, error, refetch } = useDashboard()
  if (isLoading) return <PageSkeleton rows={4} />
  if (error || !d) return <EmptyState title="Could not load the dashboard" hint={error?.message} action={<button type="button" onClick={() => void refetch()} className="text-sm font-semibold text-brand-royal underline">Try again</button>} />
  const maxSpend = Math.max(...d.top_spend.map((s) => s.total_rm), 0)

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="text-sm text-slate-600">Plan, forecast and stock overview · {fmtDay(d.today)}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Forecast accuracy"><Accuracy d={d} /></Card>

        <Card title="Latest plan">
          {!d.last_plan ? (
            <EmptyState title="No plan yet" action={<Link to="/plan" className="text-sm font-medium text-brand-royal underline">Make your first plan</Link>} />
          ) : (
            <>
              <p className="text-sm text-slate-600">
                For {d.last_plan.horizon_days} day{d.last_plan.horizon_days === 1 ? '' : 's'} ·{' '}
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
              <Link to="/plan" className="mt-2 inline-block text-sm font-medium text-brand-royal underline">Open the plan</Link>
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
            <div className="mt-3">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase text-red-800">Expired items</h3>
                <Link to="/inventory" className="text-xs font-medium text-brand-royal underline">Inventory</Link>
              </div>
              <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {d.inventory.expired_items.map((name) => (
                  <li key={name} className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-900">{name}</li>
                ))}
              </ul>
            </div>
          )}
          {d.inventory.expiring_soon > 0 && (
            <div className="mt-3">
              <h3 className="mb-2 text-xs font-semibold uppercase text-amber-800">Use soon</h3>
              <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {d.inventory.expiring_items.map((item) => (
                  <li key={item.name} className="flex items-center justify-between gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
                    <span className="min-w-0 break-words">{item.name}</span>
                    <Badge tone="warn">{item.days_left}d</Badge>
                  </li>
                ))}
              </ul>
            </div>
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
                  <div className="mt-1 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-brand-royal" style={{ width: `${maxSpend > 0 ? Math.max(0, Math.min(100, s.total_rm / maxSpend * 100)) : 0}%` }} /></div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
