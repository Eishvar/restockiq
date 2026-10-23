import { useEffect, useRef, useState } from 'react'
import { Button, EmptyState, useToast } from '../../components/ui'
import { inputCls } from '../inventory/QtyInput'
import { useSuppliers, type Supplier } from '../inventory/api'
import { useSaveSupplier } from '../settings/api'
import { rm } from './format'
import { useRole } from './GatedButton'
import { useOrders, type Order, type OrderStatus } from './api'
import SupplierCard from './SupplierCard'

type Tab = 'draft' | 'approved' | 'received'
const TABS: { id: Tab; label: string }[] = [
  { id: 'draft', label: 'Draft' },
  { id: 'approved', label: 'Approved' },
  { id: 'received', label: 'Received' },
]

function bucket(status: OrderStatus): Tab {
  if (status === 'received') return 'received'
  if (status === 'approved' || status === 'sent') return 'approved'
  return 'draft' // A submitted order is still waiting in the Draft lane for the owner's approval.
}

function SupplierDetails({ supplier }: { supplier: Supplier }) {
  const { isOwner } = useRole()
  const save = useSaveSupplier()
  const toast = useToast()
  const [whatsapp, setWhatsapp] = useState(supplier.whatsapp)
  const [minOrder, setMinOrder] = useState(String(supplier.min_order_rm))
  const minimum = Number(minOrder)
  const changed = whatsapp !== supplier.whatsapp || minimum !== supplier.min_order_rm
  const valid = minOrder.trim() !== '' && Number.isFinite(minimum) && minimum >= 0

  async function submit() {
    try {
      await save.mutateAsync({ id: supplier.id, whatsapp, min_order_rm: minimum })
      toast(`${supplier.name} saved`, 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not save supplier details', 'error')
    }
  }

  return (
    <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <h3 className="mb-2 text-sm font-semibold text-slate-800">Supplier details</h3>
      {isOwner ? (
        <div className="grid gap-2 sm:grid-cols-[1fr_12rem_auto] sm:items-end">
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-slate-500">WhatsApp number</span>
            <input type="tel" autoComplete="tel" value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} placeholder="+60123456789" className={`${inputCls} w-full`} aria-label={`WhatsApp number for ${supplier.name}`} />
            <span className="mt-1 block text-xs text-slate-500">Malaysian local number or international number with country code.</span>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-slate-500">Minimum order (RM)</span>
            <input type="number" min={0} step="1" value={minOrder} onChange={(e) => setMinOrder(e.target.value)} className={`${inputCls} w-full`} aria-label={`Minimum order for ${supplier.name}`} />
          </label>
          <Button onClick={submit} disabled={!changed || !valid || save.isPending}>
            {save.isPending ? 'Saving…' : 'Save details'}
          </Button>
        </div>
      ) : (
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          <div><dt className="text-xs text-slate-500">WhatsApp number</dt><dd>{supplier.whatsapp || 'Not set'}</dd></div>
          <div><dt className="text-xs text-slate-500">Minimum order</dt><dd>{rm(supplier.min_order_rm)}</dd></div>
        </dl>
      )}
    </div>
  )
}

function SupplierGroup({ supplier, orders, planId }: { supplier: Supplier; orders: Order[]; planId?: number }) {
  const hasDraft = orders.some((order) => ['draft', 'pending_approval'].includes(order.status))
  const hasApproved = orders.some((order) => ['approved', 'sent'].includes(order.status))
  const preferredTab: Tab = hasDraft ? 'draft' : hasApproved ? 'approved' : orders.some((order) => order.status === 'received') ? 'received' : 'draft'
  const currentPlanOrders = orders.filter((order) => order.run_id === planId)
  const activeIds = orders.filter((order) => ['draft', 'pending_approval'].includes(order.status) || order.run_id === planId).map((order) => order.id).sort((a, b) => a - b).join(',')
  const [expanded, setExpanded] = useState(() => hasDraft || currentPlanOrders.length > 0)
  const [tab, setTab] = useState<Tab>(() => preferredTab)
  const knownActiveIds = useRef(activeIds)
  useEffect(() => {
    if (activeIds !== knownActiveIds.current) {
      const previous = new Set(knownActiveIds.current ? knownActiveIds.current.split(',') : [])
      const added = activeIds.split(',').filter((id) => id && !previous.has(id))
      knownActiveIds.current = activeIds
      if (added.length) {
        setExpanded(true)
        setTab(preferredTab)
      }
    }
  }, [activeIds, preferredTab])
  const tabOrders = orders.filter((order) => bucket(order.status) === tab)
  const counts = Object.fromEntries(TABS.map(({ id }) => [id, orders.filter((order) => bucket(order.status) === id).length])) as Record<Tab, number>

  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-slate-50"
        aria-expanded={expanded}
        onClick={() => setExpanded((open) => !open)}
      >
        <span className="flex min-w-0 items-center gap-2">
          <svg aria-hidden="true" className={`shrink-0 text-black transition-transform ${expanded ? 'rotate-90' : ''}`} width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M5 2.5 11 8l-6 5.5Z"/></svg>
          <span className="truncate font-semibold text-slate-900">{supplier.name}</span>
        </span>
        <span className="shrink-0 text-xs text-slate-500">
          {counts.draft} draft · {counts.approved} approved · {counts.received} received
        </span>
      </button>

      {expanded && (
        <div className="border-t border-slate-100 p-3 sm:p-4">
          <SupplierDetails key={`${supplier.id}-${supplier.whatsapp}-${supplier.min_order_rm}`} supplier={supplier} />
          <div className="mb-3 flex flex-wrap gap-2" role="tablist" aria-label={`${supplier.name} orders`}>
            {TABS.map(({ id, label }) => (
              <Button
                key={id}
                role="tab"
                aria-selected={tab === id}
                variant={tab === id ? 'primary' : 'secondary'}
                onClick={() => setTab(id)}
              >
                {label} <span className="ml-1 opacity-75">{counts[id]}</span>
              </Button>
            ))}
          </div>
          <div role="tabpanel" aria-label={`${supplier.name} ${tab} orders`} className="space-y-3">
            {tabOrders.length ? (
              tabOrders.map((order) => <SupplierCard key={order.id} order={order} showSupplierTitle={false} />)
            ) : (
              <p className="rounded-lg bg-slate-50 px-3 py-4 text-sm text-slate-500">No {tab} orders for this supplier.</p>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

/** Every supplier gets an independent collapsible order list and three simple status tabs. */
export default function SupplierOrdersBoard({ planId }: { planId?: number }) {
  const orders = useOrders('')
  const supplierList = useSuppliers()
  if (orders.isLoading || supplierList.isLoading) return <p className="text-sm text-slate-500">Loading supplier details…</p>
  if (orders.error || supplierList.error) return <EmptyState title="Could not load supplier details" hint={orders.error?.message ?? supplierList.error?.message} />
  if (!supplierList.data?.length) return <EmptyState title="No suppliers yet" hint="Add supplier details before creating a purchase plan." />

  const grouped = new Map<number, Order[]>(supplierList.data.map((supplier) => [supplier.id, []]))
  for (const order of orders.data ?? []) {
    grouped.get(order.supplier_id)?.push(order)
  }
  const suppliers = [...supplierList.data].sort((a, b) => a.name.localeCompare(b.name))

  return (
    <div className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold">Supplier orders</h2>
        <p className="text-sm text-slate-600">Expand a supplier to manage its number and minimum order, edit draft quantities, and track orders through delivery.</p>
      </div>
      {suppliers.map((supplier) => (
        <SupplierGroup key={supplier.id} supplier={supplier} orders={grouped.get(supplier.id) ?? []} planId={planId} />
      ))}
    </div>
  )
}
