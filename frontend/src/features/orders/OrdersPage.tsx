import { useState } from 'react'
import { EmptyState, SegmentedControl } from '../../components/ui'
import { useOrders, type OrderStatus } from '../planning/api'
import { fmtDay } from '../planning/format'
import SupplierCard from '../planning/SupplierCard'

type Filter = '' | OrderStatus

const FILTERS: { value: Filter; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'pending_approval', label: 'Waiting' },
  { value: 'approved', label: 'Approved' },
  { value: 'sent', label: 'Sent' },
  { value: 'received', label: 'Received' },
  { value: 'rejected', label: 'Rejected' },
]

const stamp = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString('en-MY', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : null

/** Every order from every plan, newest first. Same cards and buttons as the Plan purchases page. */
export default function OrdersPage() {
  const [status, setStatus] = useState<Filter>('')
  const { data, isLoading, error } = useOrders(status)

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Orders</h1>
        <p className="text-sm text-slate-600">All purchase orders to your suppliers, and where each one is up to.</p>
      </div>
      <div className="overflow-x-auto pb-1">
        <SegmentedControl<Filter> label="Filter by status" options={FILTERS} value={status} onChange={setStatus} />
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {error && <EmptyState title="Could not load the orders" hint={error.message} />}
      {data && data.length === 0 && (
        <EmptyState
          title={status ? 'No orders with this status' : 'No orders yet'}
          hint={status ? 'Try another filter.' : 'Orders appear here after you generate a plan on the Plan purchases page.'}
        />
      )}
      {data?.map((o) => (
        <div key={o.id}>
          <p className="mb-1 text-xs text-slate-500">
            Order #{o.id} · plan #{o.run_id} for {fmtDay(o.plan_today)}
            {o.created_at && ` · made ${stamp(o.created_at)}`}
            {o.submitted_at && ` · submitted ${stamp(o.submitted_at)}`}
            {o.approved_at && ` · approved ${stamp(o.approved_at)}`}
            {o.sent_at && ` · sent ${stamp(o.sent_at)}`}
            {o.received_at && ` · received ${stamp(o.received_at)}`}
          </p>
          <SupplierCard order={o} />
        </div>
      ))}
    </div>
  )
}
