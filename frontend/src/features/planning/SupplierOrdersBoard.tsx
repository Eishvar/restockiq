import { useState } from 'react'
import { Button, EmptyState } from '../../components/ui'
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

function SupplierGroup({ supplier, orders }: { supplier: string; orders: Order[] }) {
  const [expanded, setExpanded] = useState(false)
  const [tab, setTab] = useState<Tab>('draft')
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
          <span aria-hidden="true" className="w-4 text-lg text-slate-500">{expanded ? '⌄' : '›'}</span>
          <span className="truncate font-semibold text-slate-900">{supplier}</span>
        </span>
        <span className="shrink-0 text-xs text-slate-500">
          {counts.draft} draft · {counts.approved} approved · {counts.received} received
        </span>
      </button>

      {expanded && (
        <div className="border-t border-slate-100 p-3 sm:p-4">
          <div className="mb-3 flex flex-wrap gap-2" role="tablist" aria-label={`${supplier} orders`}>
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
          <div role="tabpanel" aria-label={`${supplier} ${tab} orders`} className="space-y-3">
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
export default function SupplierOrdersBoard() {
  const { data, isLoading, error } = useOrders('')
  if (isLoading) return <p className="text-sm text-slate-500">Loading supplier orders…</p>
  if (error) return <EmptyState title="Could not load supplier orders" hint={error.message} />
  if (!data?.length) {
    return <EmptyState title="No supplier orders yet" hint="Generate a plan to create editable draft orders for each supplier." />
  }

  const grouped = new Map<number, { name: string; orders: Order[] }>()
  for (const order of data) {
    const group = grouped.get(order.supplier_id) ?? { name: order.supplier_name, orders: [] }
    group.orders.push(order)
    grouped.set(order.supplier_id, group)
  }
  const suppliers = [...grouped.entries()].sort((a, b) => a[1].name.localeCompare(b[1].name))

  return (
    <div className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold">Supplier orders</h2>
        <p className="text-sm text-slate-600">Adjust draft quantities before finishing. Approved orders stay here until their delivery is received.</p>
      </div>
      {suppliers.map(([supplierId, group]) => (
        <SupplierGroup key={supplierId} supplier={group.name} orders={group.orders} />
      ))}
    </div>
  )
}
