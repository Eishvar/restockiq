import { Fragment, useState } from 'react'
import { Badge, Button, Card, Modal, Tooltip, useToast } from '../../components/ui'
import { inputCls } from '../inventory/QtyInput'
import {
  useEditLine,
  useOrderAction,
  usePrepareOrderMessage,
  type Line,
  type Order,
  type OrderStatus,
  type SendResult,
} from './api'
import { effectiveSchedule, fmtDay, rm } from './format'
import GatedButton, { useRole } from './GatedButton'
import { bufferTooltip, whySentences } from './why'

function Stepper({ status }: { status: OrderStatus }) {
  if (status === 'rejected') return <Badge tone="bad">Rejected</Badge>
  const active = status === 'received' ? 'received' : status === 'approved' || status === 'sent' ? 'approved' : 'draft'
  const steps: { status: string; label: string }[] = [
    { status: 'draft', label: 'Draft' },
    { status: 'approved', label: 'Approved' },
    { status: 'received', label: 'Received' },
  ]
  return (
    <ol className="flex flex-wrap items-center gap-1 text-xs" aria-label="Order progress">
      {steps.map((s, i) => {
        const at = steps.findIndex((step) => step.status === active)
        return (
        <li key={s.status} className="flex items-center gap-1">
          <span
            aria-current={i === at ? 'step' : undefined}
            className={`rounded-full px-2 py-0.5 ${i < at ? 'bg-emerald-100 text-emerald-800' : i === at ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-500'}`}
          >
            {s.label}
          </span>
          {i < steps.length - 1 && <span className="text-slate-300">›</span>}
        </li>
        )
      })}
    </ol>
  )
}

function When({ line }: { line: Line }) {
  const trips = effectiveSchedule(line.buy_schedule, line.suggested_packs, line.final_packs)
  return (
    <div className="space-y-0.5">
      {trips.map((t) => (
        <div key={t.date} className="whitespace-nowrap">
          {fmtDay(t.date)} <span className="text-slate-500">× {t.packs}</span>
        </div>
      ))}
    </div>
  )
}

function Buffer({ line }: { line: Line }) {
  return (
    <Tooltip text={bufferTooltip(line)}>
      <span className="cursor-help underline decoration-dotted">+{line.buffer_pct}%</span>
    </Tooltip>
  )
}

function Stock({ line }: { line: Line }) {
  const s = line.explanation.stock
  if (s.expired) return <span className="text-red-700">expired, not counted</span>
  return (
    <span>
      {line.display_usable_stock}
      {s.expires_on && line.usable_stock_base > 0 && <span className="block text-xs text-slate-500">good until {fmtDay(s.expires_on)}</span>}
    </span>
  )
}

/** Pack count: editable by managers while the order is a draft, plain text otherwise. */
function Buy({ line, order, editable }: { line: Line; order: Order; editable: boolean }) {
  const edit = useEditLine()
  const toast = useToast()
  const [text, setText] = useState(String(line.final_packs))
  const [seen, setSeen] = useState(line.final_packs)
  if (seen !== line.final_packs) {
    setSeen(line.final_packs)
    setText(String(line.final_packs))
  }
  if (!editable) return <span>{line.display_buy}</span>

  async function commit() {
    const n = parseInt(text)
    if (Number.isNaN(n) || n < 0) return setText(String(line.final_packs))
    if (n === line.final_packs) return
    try {
      await edit.mutateAsync({ orderId: order.id, lineId: line.id, finalPacks: n })
    } catch (err) {
      setText(String(line.final_packs))
      toast(err instanceof Error ? err.message : 'Could not change the amount', 'error')
    }
  }

  return (
    <span className="inline-flex items-center gap-1">
      <input
        type="number"
        min={0}
        inputMode="numeric"
        aria-label={`Packs of ${line.name}`}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
        className={`${inputCls} w-16`}
      />
      <span className="text-xs text-slate-500">{line.pack_uom}</span>
    </span>
  )
}

function Why({ line }: { line: Line }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
      {whySentences(line).map((s, i) => (
        <p key={i} className={i ? 'mt-1' : ''}>{s}</p>
      ))}
    </div>
  )
}

export default function SupplierCard({ order, showSupplierTitle = true }: { order: Order; showSupplierTitle?: boolean }) {
  const { isOwner, isManager } = useRole()
  const act = useOrderAction()
  const prepareMessage = usePrepareOrderMessage()
  const toast = useToast()
  const [open, setOpen] = useState<number | null>(null)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState<SendResult | null>(null)
  const [finishing, setFinishing] = useState(false)

  const draft = order.status === 'draft'
  const editable = draft && isManager
  const run = async (action: 'submit' | 'approve' | 'receive', done: string) => {
    try {
      await act.mutateAsync({ orderId: order.id, action })
      toast(done, 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Something went wrong', 'error')
    }
  }

  async function finishAndApprove() {
    setFinishing(true)
    try {
      setMessage(await prepareMessage.mutateAsync(order.id))
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not prepare the order message', 'error')
    } finally {
      setFinishing(false)
    }
  }

  async function confirmPlaced() {
    if (!message) return
    setFinishing(true)
    try {
      let current = message.order.status
      if (current === 'draft') {
        const submitted = (await act.mutateAsync({ orderId: order.id, action: 'submit' })) as Order
        current = submitted.status
        setMessage((previous) => previous ? { ...previous, order: submitted } : previous)
      }
      if (current === 'pending_approval') {
        await act.mutateAsync({ orderId: order.id, action: 'approve' })
      }
      setMessage(null)
      toast('Order placed and moved to Approved.', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not update the order status', 'error')
    } finally {
      setFinishing(false)
    }
  }

  async function reject() {
    try {
      await act.mutateAsync({ orderId: order.id, action: 'reject', reason })
      toast('Order rejected', 'success')
      setRejecting(false)
      setReason('')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not reject', 'error')
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(message?.whatsapp_text ?? '')
      toast('Message copied', 'success')
    } catch {
      toast('Could not copy. Select the text and copy it by hand.', 'error')
    }
  }

  const lines = order.lines
  const actions = (
    <div className="flex flex-wrap items-center gap-2">
      {draft && (
        isOwner ? (
          <GatedButton allowed={isOwner} need="owner" verb="approve orders" onClick={finishAndApprove} disabled={act.isPending || finishing}>
            Review & place order
          </GatedButton>
        ) : (
          <GatedButton allowed={isManager} need="manager" verb="submit orders" onClick={() => run('submit', 'Finished. The owner can now approve it.')} disabled={act.isPending}>
            Finish & submit
          </GatedButton>
        )
      )}
      {order.status === 'pending_approval' && (
        <>
          <GatedButton allowed={isOwner} need="owner" verb="approve orders" onClick={finishAndApprove} disabled={act.isPending || finishing}>
            Review & place order
          </GatedButton>
          <GatedButton allowed={isOwner} need="owner" verb="reject orders" variant="danger" onClick={() => setRejecting(true)} disabled={act.isPending}>
            Reject
          </GatedButton>
        </>
      )}
      {order.status === 'approved' && (
        <>
          <GatedButton allowed={isOwner} need="owner" verb="contact suppliers" onClick={finishAndApprove} disabled={act.isPending || finishing}>
            Contact supplier
          </GatedButton>
          <GatedButton allowed={isManager} need="manager" verb="mark deliveries as received" onClick={() => run('receive', 'Stock updated with this delivery')} disabled={act.isPending}>
            Mark received
          </GatedButton>
        </>
      )}
      {order.status === 'sent' && (
        <>
          <GatedButton allowed={isOwner} need="owner" verb="reopen the WhatsApp message" variant="secondary" onClick={finishAndApprove} disabled={act.isPending || finishing}>
            Open WhatsApp / copy
          </GatedButton>
          <GatedButton allowed={isManager} need="manager" verb="mark deliveries as received" onClick={() => run('receive', 'Stock updated with this delivery')} disabled={act.isPending}>
            Mark received
          </GatedButton>
        </>
      )}
      {order.status === 'received' && <span className="text-sm text-emerald-700">Delivered and added to your stock.</span>}
    </div>
  )

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          {showSupplierTitle ? (
            <h3 className="text-base font-semibold">{order.supplier_name}</h3>
          ) : (
            <h3 className="text-sm font-semibold">Order #{order.id} · plan #{order.run_id} ({order.plan_today})</h3>
          )}
          <p className="text-xs text-slate-500">
            {lines.length} item{lines.length === 1 ? '' : 's'}
            {order.created_at ? ` · created ${fmtDay(order.created_at.slice(0, 10))}` : ''}
            {order.approved_by_name ? ` · approved by ${order.approved_by_name}` : ''}
          </p>
        </div>
        <div className="text-right text-lg font-semibold">{rm(order.total_rm)}</div>
      </div>
      <div className="mt-2">
        <Stepper status={order.status} />
        {order.status === 'rejected' && order.reject_reason && (
          <p className="mt-1 text-sm text-red-700">Reason: {order.reject_reason}</p>
        )}
      </div>
      {order.warnings.map((w) => (
        <p key={w} className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">⚠ {w}</p>
      ))}

      {/* Wide screens: a table */}
      <div className="mt-3 hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
            <tr>
              {['Item', 'Need', 'Safety buffer', 'Usable stock', 'Buy', 'When', 'Pack price', 'Total', ''].map((h) => (
                <th key={h} className="px-2 py-2 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 align-top [&_td]:px-2 [&_td]:py-2">
            {lines.map((l) => (
              <Fragment key={l.id}>
                <tr>
                  <td className="font-medium">{l.name}</td>
                  <td className="whitespace-nowrap">{l.display_need}</td>
                  <td><Buffer line={l} /></td>
                  <td><Stock line={l} /></td>
                  <td><Buy line={l} order={order} editable={editable} /></td>
                  <td><When line={l} /></td>
                  <td className="whitespace-nowrap">{rm(l.pack_price_rm)}</td>
                  <td className="whitespace-nowrap font-medium">{rm(l.line_total_rm)}</td>
                  <td>
                    <Button variant="ghost" onClick={() => setOpen(open === l.id ? null : l.id)} aria-expanded={open === l.id}>
                      Why?
                    </Button>
                  </td>
                </tr>
                {open === l.id && (
                  <tr>
                    <td colSpan={9}><Why line={l} /></td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Phones: one card per item */}
      <div className="mt-3 space-y-3 md:hidden">
        {lines.map((l) => (
          <div key={l.id} className="rounded-lg border border-slate-200 p-3 text-sm">
            <div className="flex items-start justify-between gap-2">
              <div className="font-medium">{l.name}</div>
              <div className="font-semibold">{rm(l.line_total_rm)}</div>
            </div>
            <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
              <dt className="text-slate-500">Need</dt><dd>{l.display_need}</dd>
              <dt className="text-slate-500">Safety buffer</dt><dd><Buffer line={l} /></dd>
              <dt className="text-slate-500">Usable stock</dt><dd><Stock line={l} /></dd>
              <dt className="text-slate-500">Buy</dt><dd><Buy line={l} order={order} editable={editable} /></dd>
              <dt className="text-slate-500">When</dt><dd><When line={l} /></dd>
              <dt className="text-slate-500">Pack price</dt><dd>{rm(l.pack_price_rm)}</dd>
            </dl>
            <Button variant="ghost" className="mt-1 px-0" onClick={() => setOpen(open === l.id ? null : l.id)} aria-expanded={open === l.id}>
              Why?
            </Button>
            {open === l.id && <Why line={l} />}
          </div>
        ))}
      </div>

      <div className="mt-4 border-t border-slate-100 pt-3">{actions}</div>

      <Modal open={rejecting} title={`Reject the order to ${order.supplier_name}?`} onClose={() => setRejecting(false)}>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Why? (the manager will see this)</span>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} maxLength={300} className={`${inputCls} w-full`} />
        </label>
        <div className="mt-3 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setRejecting(false)}>Cancel</Button>
          <Button variant="danger" onClick={reject} disabled={!reason.trim() || act.isPending}>Reject order</Button>
        </div>
      </Modal>

      <Modal open={message !== null} title={`Place order · ${order.supplier_name}`} onClose={() => setMessage(null)}>
        <p className="mb-2 text-sm text-slate-600">
          {message?.order.status === 'draft' || message?.order.status === 'pending_approval'
            ? 'Contact the supplier, then confirm below. The order stays in Draft until you confirm.'
            : 'Contact the supplier about this order.'}
        </p>
        {message?.call_url ? (
          <p className="mb-2 text-sm font-medium text-slate-800">
            Supplier number: {message.call_url.slice(4)}
          </p>
        ) : (
          <p role="alert" className="mb-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
            Add a valid phone number in this supplier’s details to use WhatsApp or Call.
          </p>
        )}
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm">{message?.whatsapp_text}</pre>
        <div className="mt-3 flex flex-wrap justify-between gap-2">
          <Button variant="secondary" onClick={() => setMessage(null)}>Cancel</Button>
          <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={copy}>Copy message</Button>
          {message?.call_url && (
            <a href={message.call_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
              Call supplier
            </a>
          )}
          {message?.whatsapp_url && (
            <a href={message.whatsapp_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700">
              Open WhatsApp
            </a>
          )}
          {message?.order.status === 'draft' || message?.order.status === 'pending_approval' ? (
            <Button onClick={confirmPlaced} disabled={finishing || act.isPending}>
              {finishing ? 'Updating order…' : 'I have placed the order'}
            </Button>
          ) : (
            <Button onClick={() => setMessage(null)}>Done</Button>
          )}
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          WhatsApp opens with your message ready to send. Calls open your phone or calling app; a computer needs a calling app configured.
        </p>
      </Modal>
    </Card>
  )
}
