import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, EmptyState, PageSkeleton } from '../../components/ui'
import { inputCls } from '../inventory/QtyInput'
import { fmtDayYear, rm } from '../planning/format'
import { useOrders, type Order, type OrderStatus } from '../planning/api'

type StatusInfo = { label: string; tone: 'neutral' | 'good' | 'warn' | 'bad' }
const STATUS: Record<OrderStatus, StatusInfo> = {
  draft: { label: 'Draft', tone: 'neutral' },
  pending_approval: { label: 'Pending approval', tone: 'warn' },
  approved: { label: 'Approved', tone: 'good' },
  sent: { label: 'Sent', tone: 'good' },
  received: { label: 'Received', tone: 'good' },
  rejected: { label: 'Rejected', tone: 'bad' },
}

const FILTERS: { value: 'all' | OrderStatus; label: string }[] = [
  { value: 'all', label: 'All statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'pending_approval', label: 'Pending approval' },
  { value: 'approved', label: 'Approved' },
  { value: 'sent', label: 'Sent' },
  { value: 'received', label: 'Received' },
  { value: 'rejected', label: 'Rejected' },
]

function showDate(value: string | null) {
  return value ? fmtDayYear(value.slice(0, 10)) : '—'
}

function OrderRecord({ order }: { order: Order }) {
  const status = STATUS[order.status]
  return (
    <details className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 hover:bg-slate-50 [&::-webkit-details-marker]:hidden">
        <span className="min-w-0">
          <span className="block truncate font-semibold text-slate-900">{order.supplier_name}</span>
          <span className="mt-0.5 block text-sm text-slate-500">
            Created {showDate(order.created_at)} · {order.lines.length} item{order.lines.length === 1 ? '' : 's'}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <Badge tone={status.tone}>{status.label}</Badge>
          <span className="font-semibold text-slate-900">{rm(order.total_rm)}</span>
          <svg aria-hidden="true" className="text-slate-400" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m6 9 6 6 6-6"/></svg>
        </span>
      </summary>
      <div className="border-t border-slate-100 px-4 py-3">
        <ul className="divide-y divide-slate-100">
          {order.lines.map((line) => (
            <li key={line.id} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 py-2 text-sm">
              <span className="min-w-0 break-words font-medium text-slate-800">{line.name}</span>
              <span className="text-slate-600">{line.display_buy}</span>
              <span className="text-right text-slate-700">{rm(line.line_total_rm)}</span>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-100 pt-3 text-xs text-slate-500">
          {order.approved_at && <span>Approved {showDate(order.approved_at)}</span>}
          {order.sent_at && <span>Sent {showDate(order.sent_at)}</span>}
          {order.received_at && <span>Received {showDate(order.received_at)}</span>}
          {order.approved_by_name && <span>Approved by {order.approved_by_name}</span>}
        </div>
        {order.reject_reason && (
          <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
            Rejection reason: {order.reject_reason}
          </p>
        )}
        {order.warnings.length > 0 && (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-amber-800">
            {order.warnings.map((warning, index) => <li key={index}>{warning}</li>)}
          </ul>
        )}
      </div>
    </details>
  )
}

export default function OrdersPage() {
  const orders = useOrders('')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<'all' | OrderStatus>('all')

  if (orders.isLoading) return <PageSkeleton rows={4} />
  if (orders.error) return <EmptyState title="Could not load order history" hint={orders.error.message} action={<button type="button" onClick={() => void orders.refetch()} className="text-sm font-semibold text-brand-royal underline">Try again</button>} />
  if (!orders.data?.length) {
    return (
      <div className="mx-auto max-w-6xl space-y-4">
        <PageHeading />
        <EmptyState title="No orders yet" hint="Orders created from purchase plans will appear here." action={<Link to="/plan" className="text-sm font-medium text-brand-royal underline">Open Plan purchases</Link>} />
      </div>
    )
  }

  const filtered = [...orders.data]
    .filter((order) => status === 'all' || order.status === status)
    .filter((order) => order.supplier_name.toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => {
      const dateA = a.created_at ?? a.plan_today
      const dateB = b.created_at ?? b.plan_today
      return dateB.localeCompare(dateA) || b.id - a.id
    })

  return (
    <div className="mx-auto max-w-6xl space-y-4 pb-6">
      <PageHeading />
      <div className="flex flex-wrap items-center gap-2">
        <label className="min-w-48 flex-1">
          <span className="sr-only">Search supplier names</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search suppliers"
            className={`${inputCls} w-full`}
          />
        </label>
        <label>
          <span className="sr-only">Filter by status</span>
          <select value={status} onChange={(event) => setStatus(event.target.value as 'all' | OrderStatus)} className={inputCls}>
            {FILTERS.map((filter) => <option key={filter.value} value={filter.value}>{filter.label}</option>)}
          </select>
        </label>
      </div>
      {filtered.length ? (
        <div className="space-y-2">
          {filtered.map((order) => <OrderRecord key={order.id} order={order} />)}
        </div>
      ) : (
        <EmptyState title="No matching orders" hint="Try a different supplier name or status." />
      )}
    </div>
  )
}

function PageHeading() {
  return (
    <div>
      <h1 className="text-xl font-semibold">Order history</h1>
    </div>
  )
}
