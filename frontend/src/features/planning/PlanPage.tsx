import { useState } from 'react'
import { Card, EmptyState, PageSkeleton, SegmentedControl, Table, useToast } from '../../components/ui'
import { ApiError } from '../../api/client'
import { useGeneratePlan, usePlan, usePlanContext, type Plan } from './api'
import ForecastCard from './ForecastCard'
import { fmtDay, fmtDayYear, formatQty, rm } from './format'
import GatedButton, { useRole } from './GatedButton'
import SupplierOrdersBoard from './SupplierOrdersBoard'

const HORIZONS = [1, 2, 3, 4, 5, 6, 7].map((n) => ({ value: n, label: String(n) }))

/** Compact list of stock and recipe checks that may need action. */
function Attention({ plan }: { plan: Plan }) {
  const items: { name: string; issue: string }[] = []
  const unused: string[] = []
  for (const e of plan.exceptions) {
    const name = String(e.name ?? '')
    if (e.type === 'short_today')
      items.push({ name, issue: `Short by ${formatQty(Number(e.short_base), String(e.base_uom))}` })
    else if (e.type === 'dish_without_recipe') items.push({ name: name || 'Unnamed dish', issue: 'No recipe' })
    else if (e.type === 'no_supplier')
      for (const itemName of (e.names as string[])) items.push({ name: itemName, issue: 'No supplier' })
    else if (e.type === 'no_forecast_use') unused.push(name)
  }
  if (!items.length && !unused.length) return null
  const count = items.length + unused.length
  const visibleItems = items.slice(0, 4)
  const remainingItems = items.slice(4)
  const renderItems = (rows: typeof items) => rows.map((item, i) => (
    <li key={`${item.name}-${i}`} className="flex items-center justify-between gap-3 py-2">
      <span className="min-w-0 truncate font-medium text-slate-800">{item.name}</span>
      <span className="shrink-0 text-right text-slate-600">{item.issue}</span>
    </li>
  ))
  return (
    <Card title={`Plan checks (${count})`}>
      {items.length > 0 && (
        <ul className="divide-y divide-slate-100 text-sm">
          {renderItems(visibleItems)}
        </ul>
      )}
      {remainingItems.length > 0 && (
        <details className="mt-2 border-t border-slate-100 pt-2 text-sm">
          <summary className="cursor-pointer font-medium text-slate-700">Show {remainingItems.length} more checks</summary>
          <ul className="mt-1 divide-y divide-slate-100">{renderItems(remainingItems)}</ul>
        </details>
      )}
      {unused.length > 0 && (
        <details className={`${items.length ? 'mt-2 border-t border-slate-100 pt-2' : ''} text-sm`}>
          <summary className="cursor-pointer font-medium text-slate-700">{unused.length} items with no forecast use</summary>
          <ul className="mt-2 grid grid-cols-1 gap-1 text-slate-600 sm:grid-cols-2">
            {unused.map((name, i) => <li key={`${name}-${i}`} className="truncate">{name}</li>)}
          </ul>
        </details>
      )}
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
            Plan #{p.id} · bought for {p.horizon_days} day{p.horizon_days === 1 ? '' : 's'} from tomorrow · {p.risk_profile.replace(/_/g, ' ')} stock setting
          </p>
          <ForecastCard plan={p} />
          <Attention plan={p} />
          <DiscardList plan={p} />
          {p.orders.length === 0 && <EmptyState title="Nothing to buy" hint="Your current stock covers everything for these days." />}
          {p.covered.length > 0 && (
            <details className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
              <summary className="cursor-pointer font-medium">Covered by stock ({p.covered.length})</summary>
              <ul className="mt-3 grid grid-cols-1 gap-1 text-slate-600 sm:grid-cols-2 lg:grid-cols-3">
                {p.covered.map((c) => <li key={c.ingredient_id} className="truncate">{c.name}</li>)}
              </ul>
            </details>
          )}
          <div id="supplier-orders" className="scroll-mt-24"><SupplierOrdersBoard planId={p.id} /></div>
        </>
      )}

      {p && p.orders.length > 0 && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:left-60">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2">
            <div className="text-sm text-slate-600">
              {active.length} order{active.length === 1 ? '' : 's'} · {active.filter((o) => ['approved', 'sent', 'received'].includes(o.status)).length} approved
            </div>
            <button type="button" onClick={() => document.getElementById('supplier-orders')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} className="inline-flex min-h-9 items-center gap-1 text-sm font-semibold text-brand-royal underline underline-offset-2">Review supplier orders <svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 4v16m-7-7 7 7 7-7"/></svg></button>
            <div className="text-lg font-semibold">Grand total {rm(total)}</div>
          </div>
        </div>
      )}
    </div>
  )
}
