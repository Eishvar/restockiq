import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { Card, EmptyState, PageSkeleton, SegmentedControl, useToast } from '../../components/ui'
import { ApiError } from '../../api/client'
import { useGeneratePlan, usePlan, usePlanContext, type Plan } from './api'
import ForecastCard from './ForecastCard'
import PlanOverview from './PlanOverview'
import { useDashboard } from '../dashboard/api'
import { forecastAccuracyPercent } from '../dashboard/accuracy'
import { fmtDay, fmtDayYear, formatQty, rm } from './format'
import GatedButton, { useRole } from './GatedButton'
import SupplierOrdersBoard from './SupplierOrdersBoard'

const HORIZONS = [1, 2, 3, 4, 5, 6, 7].map((n) => ({ value: n, label: String(n) }))

function DiscardList({ plan }: { plan: Plan }) {
  if (!plan.discard.length) return null
  const n = plan.discard.length
  return (
    <section role="alert" className="overflow-hidden rounded-2xl border border-red-300 bg-red-50 shadow-sm">
      <div className="flex flex-wrap items-center gap-3 border-b border-red-200 bg-red-100 px-4 py-3">
        <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-600 text-white">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3 2 20h20L12 3Z"/><path d="M12 10v5M12 18h.01"/></svg>
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-bold text-red-900">{n} expired item{n === 1 ? '' : 's'}</h2>
          <p className="text-sm text-red-800">Excluded from this plan. Remove them from stock so they are not used.</p>
        </div>
        <Link to="/inventory" className="inline-flex min-h-9 items-center rounded-lg bg-red-600 px-3 text-sm font-semibold text-white hover:bg-red-700">Open Inventory</Link>
      </div>
      <ul className="divide-y divide-red-200">
        {plan.discard.map((d, i) => (
          <li key={`${d.ingredient_id}-${i}`} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3">
            <span className="font-semibold text-red-950">{d.name}</span>
            <span className="flex flex-wrap items-center gap-3 text-sm">
              <span className="tabular-nums text-red-900">{formatQty(d.qty_base, d.base_uom)}</span>
              <span className="rounded-full bg-red-600 px-2.5 py-0.5 text-xs font-semibold text-white">Expired {d.days_ago} day{d.days_ago === 1 ? '' : 's'} ago</span>
              <span className="text-red-800">{fmtDay(d.expired_on)}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function PlanPage() {
  const ctx = usePlanContext()
  const generate = useGeneratePlan()
  const toast = useToast()
  const { isManager } = useRole()
  const [horizon, setHorizon] = useState(3)
  const [justMade, setJustMade] = useState<number | null>(null)
  const planId = justMade ?? ctx.data?.last_plan_id ?? null
  const plan = usePlan(planId)
  const dash = useDashboard()
  const wape = dash.data?.accuracy?.wape_total
  const accuracy = typeof wape === 'number' && Number.isFinite(wape) && wape >= 0 ? forecastAccuracyPercent(wape) : null

  async function onGenerate() {
    try {
      const p = await generate.mutateAsync(horizon)
      setJustMade(p.id)
    } catch (err) {
      toast(err instanceof ApiError || err instanceof Error ? err.message : 'Could not make the plan', 'error')
    }
  }

  const p = plan.data
  const active = p?.orders.filter((o) => o.status !== 'rejected') ?? []
  const total = active.reduce((sum, o) => sum + o.total_rm, 0)

  return (
    <div className="mx-auto max-w-6xl space-y-4 pb-36 md:pb-24">
      <div>
        <h1 className="text-xl font-semibold">Plan purchases</h1>
      </div>

      <Card>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div>
            <div className="text-xs uppercase text-slate-500">Today</div>
            <div className="font-medium">{ctx.data ? fmtDayYear(ctx.data.today) : '…'}</div>
          </div>
          <div>
            <div className="mb-1 text-xs uppercase text-slate-500">Buy for how many days ahead?</div>
            <SegmentedControl label="Days ahead" options={HORIZONS} value={horizon} onChange={setHorizon} />
          </div>
          <GatedButton allowed={isManager} need="manager" verb="make a plan" onClick={onGenerate} disabled={generate.isPending} className="sm:ml-auto">
            {generate.isPending ? 'Working it out…' : 'Generate plan'}
          </GatedButton>
        </div>
      </Card>

      {(ctx.isLoading || plan.isLoading) && <PageSkeleton rows={3} />}
      {ctx.error && <EmptyState title="Could not load planning data" hint={ctx.error.message} action={<button type="button" onClick={() => void ctx.refetch()} className="text-sm font-semibold text-brand-royal underline">Try again</button>} />}
      {plan.error && <EmptyState title="Could not load the plan" hint={plan.error.message} action={<button type="button" onClick={() => void plan.refetch()} className="text-sm font-semibold text-brand-royal underline">Try again</button>} />}

      {!p && !ctx.isLoading && !ctx.error && !plan.isLoading && !plan.error && (
        <EmptyState
          title="No plan yet"
          hint="Choose the number of days and generate a purchase plan."
        />
      )}

      {p && (
        <>
          <p className="text-sm text-slate-600">
            Plan #{p.id} · {p.horizon_days} day{p.horizon_days === 1 ? '' : 's'} from tomorrow · {p.risk_profile.replace(/_/g, ' ')} stock setting
          </p>
          <ForecastCard plan={p} accuracy={accuracy} />
          {dash.data && <PlanOverview d={dash.data} />}
          {p.orders.length === 0 && <EmptyState title="Nothing to buy" hint="Your current stock covers everything for these days." />}
          {p.covered.length > 0 && (
            <details className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
              <summary className="cursor-pointer font-medium">Covered by stock ({p.covered.length})</summary>
              <ul className="mt-3 grid grid-cols-1 gap-1 text-slate-600 sm:grid-cols-2 lg:grid-cols-3">
                {p.covered.map((c) => <li key={c.ingredient_id} className="truncate">{c.name}</li>)}
              </ul>
            </details>
          )}
          <DiscardList plan={p} />
          <div id="supplier-orders" className="scroll-mt-24"><SupplierOrdersBoard planId={p.id} /></div>
        </>
      )}

      {p && p.orders.length > 0 && (
        createPortal(
          <div className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:left-[var(--sidebar-w,15rem)]">
            <div className="mx-auto flex max-w-6xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="text-sm text-slate-600">
                {active.length} order{active.length === 1 ? '' : 's'} · {active.filter((o) => ['approved', 'sent', 'received'].includes(o.status)).length} approved
              </div>
              <div className="flex flex-col items-end gap-1 sm:flex-row sm:justify-end sm:gap-6">
                <button type="button" onClick={() => document.getElementById('supplier-orders')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} className="inline-flex min-h-9 items-center gap-1 text-sm font-semibold text-brand-royal underline underline-offset-2">Review supplier orders <svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 4v16m-7-7 7 7 7-7"/></svg></button>
                <div className="whitespace-nowrap text-right text-lg font-semibold">Grand total {rm(total)}</div>
              </div>
            </div>
          </div>,
          document.body,
        )
      )}
    </div>
  )
}
