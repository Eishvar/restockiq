import { useState } from 'react'
import { Card, EmptyState, SegmentedControl, Table, useToast } from '../../components/ui'
import { ApiError } from '../../api/client'
import { useGeneratePlan, usePlan, usePlanContext, type Plan } from './api'
import ForecastCard from './ForecastCard'
import { fmtDay, fmtDayYear, formatQty, num, rm } from './format'
import GatedButton, { useRole } from './GatedButton'
import SupplierOrdersBoard from './SupplierOrdersBoard'

const HORIZONS = [1, 2, 3, 4, 5, 6, 7].map((n) => ({ value: n, label: String(n) }))

/** "Done in 2.1 s · 4,712 calculations · about 2 days of manual work" */
function TimeSavedBanner({ plan }: { plan: Plan }) {
  const seconds = Math.max(plan.duration_ms / 1000, 0.1)
  const hours = plan.manual_planning_hours
  const manual = hours >= 8 ? `${num(hours / 8, 1)} day${hours / 8 === 1 ? '' : 's'}` : `${num(hours, 1)} hours`
  return (
    <div className="rounded-xl bg-emerald-600 px-4 py-3 text-white shadow-sm" role="status">
      <span className="text-lg font-semibold">Done in {num(seconds, 1)} s</span>
      <span className="mx-2 opacity-60">·</span>
      <span>{num(plan.calc_count, 0)} calculations</span>
      <span className="mx-2 opacity-60">·</span>
      <span>about {manual} of manual work</span>
    </div>
  )
}

/** Things a person has to look at, in plain words. */
function Attention({ plan }: { plan: Plan }) {
  const items: string[] = []
  const unused: string[] = []
  for (const e of plan.exceptions) {
    const name = String(e.name ?? '')
    if (e.type === 'short_today')
      items.push(`${name}: today's expected use is ${formatQty(Number(e.short_base), String(e.base_uom))} more than you have, so you may run out before the next delivery.`)
    else if (e.type === 'dish_without_recipe') items.push(`${name || 'A dish'} sells but has no recipe, so its ingredients are not planned.`)
    else if (e.type === 'no_supplier') items.push(`No supplier is set for: ${(e.names as string[]).join(', ')}.`)
    else if (e.type === 'no_forecast_use') unused.push(name)
  }
  if (unused.length) items.push(`${unused.length} item${unused.length === 1 ? ' is' : 's are'} not used by any recipe, so nothing is planned for ${unused.length === 1 ? 'it' : 'them'}: ${unused.join(', ')}.`)
  if (!items.length) return null
  return (
    <Card title={`Needs your attention (${items.length})`}>
      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
        {items.map((t, i) => <li key={i}>{t}</li>)}
      </ul>
    </Card>
  )
}

function DiscardList({ plan }: { plan: Plan }) {
  if (!plan.discard.length) return null
  return (
    <Card title={`Throw away (${plan.discard.length})`}>
      <p className="mb-2 text-sm text-slate-600">These have passed their shelf life. They are not counted as stock. Discard them on the Inventory page.</p>
      <Table head={['Item', 'How much', 'Expired']}>
        {plan.discard.map((d, i) => (
          <tr key={`${d.ingredient_id}-${i}`}>
            <td className="font-medium">{d.name}</td>
            <td>{formatQty(d.qty_base, d.base_uom)}</td>
            <td>{fmtDay(d.expired_on)} ({d.days_ago} day{d.days_ago === 1 ? '' : 's'} ago)</td>
          </tr>
        ))}
      </Table>
    </Card>
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
    <div className="mx-auto max-w-6xl space-y-4 pb-24">
      <div>
        <h1 className="text-xl font-semibold">Plan purchases</h1>
        <p className="text-sm text-slate-600">Pick how many days to buy for. We work out what to buy, how much and when.</p>
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

      {(ctx.isLoading || plan.isLoading) && <p className="text-sm text-slate-500">Loading…</p>}
      {plan.error && <EmptyState title="Could not load the plan" hint={plan.error.message} />}

      {!p && !ctx.isLoading && !plan.isLoading && !plan.error && (
        <EmptyState
          title="No plan yet"
          hint="Choose the number of days and press Generate plan. It takes a few seconds."
        />
      )}

      {p && (
        <>
          <TimeSavedBanner plan={p} />
          <p className="text-sm text-slate-600">
            Plan #{p.id} · bought for {p.horizon_days} day{p.horizon_days === 1 ? '' : 's'} from tomorrow · {p.risk_profile.replace(/_/g, ' ')} stock setting
          </p>
          <ForecastCard plan={p} />
          <Attention plan={p} />
          <DiscardList plan={p} />
          {p.orders.length === 0 && <EmptyState title="Nothing to buy" hint="Your current stock covers everything for these days." />}
          {p.covered.length > 0 && (
            <details className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
              <summary className="cursor-pointer font-medium">Nothing to buy for {p.covered.length} items (your stock already covers them)</summary>
              <p className="mt-2 text-slate-600">{p.covered.map((c) => c.name).join(', ')}</p>
            </details>
          )}
          <SupplierOrdersBoard />
        </>
      )}

      {p && p.orders.length > 0 && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:left-56">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
            <div className="text-sm text-slate-600">
              {active.length} order{active.length === 1 ? '' : 's'} · {active.filter((o) => ['approved', 'sent', 'received'].includes(o.status)).length} approved
            </div>
            <div className="text-lg font-semibold">Grand total {rm(total)}</div>
          </div>
        </div>
      )}
    </div>
  )
}
