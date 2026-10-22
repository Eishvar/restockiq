import { Fragment, useState } from 'react'
import { Badge, Button, Card, Modal, Tooltip, useToast } from '../../components/ui'
import { inputCls } from '../inventory/QtyInput'
import { useEditLine, useOrderAction, type Line, type Order, type OrderStatus, type SendResult } from './api'
import { effectiveSchedule, fmtDay, rm } from './format'
import GatedButton, { useRole } from './GatedButton'
import { bufferTooltip, whySentences } from './why'

const STEPS: { status: OrderStatus; label: string }[] = [
  { status: 'draft', label: 'Draft' },
  { status: 'pending_approval', label: 'Waiting for approval' },
  { status: 'approved', label: 'Approved' },
  { status: 'sent', label: 'Sent' },
  { status: 'received', label: 'Received' },
]

function Stepper({ status }: { status: OrderStatus }) {
  if (status === 'rejected') return <Badge tone="bad">Rejected</Badge>
  const at = STEPS.findIndex((s) => s.status === status)
  return (
    <ol className="flex flex-wrap items-center gap-1 text-xs" aria-label="Order progress">
      {STEPS.map((s, i) => (
        <li key={s.status} className="flex items-center gap-1">
          <span
            aria-current={i === at ? 'step' : undefined}
            className={`rounded-full px-2 py-0.5 ${i < at ? 'bg-emerald-100 text-emerald-800' : i === at ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-500'}`}
          >
            {s.label}
          </span>
          {i < STEPS.length - 1 && <span className="text-slate-300">›</span>}
        </li>
      ))}
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

export default function SupplierCard({ order }: { order: Order }) {
  const { isOwner, isManager } = useRole()
  const act = useOrderAction()
  const toast = useToast()
  const [open, setOpen] = useState<number | null>(null)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState<SendResult | null>(null)

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

  async function send() {
    try {
      const res = (await act.mutateAsync({ orderId: order.id, action: 'send' })) as SendResult
      setMessage(res)
      if (order.status === 'approved') toast('Marked as sent. Open WhatsApp to send the message.', 'success')
      if (res.whatsapp_url) window.open(res.whatsapp_url, '_blank', 'noopener')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not prepare the message', 'error')
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
        <GatedButton allowed={isManager} need="manager" verb="submit orders" onClick={() => run('submit', 'Submitted. The owner can now approve it.')} disabled={act.isPending}>
          Submit for approval
        </GatedButton>
      )}
      {order.status === 'pending_approval' && (
        <>
          <GatedButton allowed={isOwner} need="owner" verb="approve orders" onClick={() => run('approve', 'Approved')} disabled={act.isPending}>
            Approve
          </GatedButton>
          <GatedButton allowed={isOwner} need="owner" verb="reject orders" variant="danger" onClick={() => setRejecting(true)} disabled={act.isPending}>
            Reject
          </GatedButton>
        </>
      )}
      {order.status === 'approved' && (
        <GatedButton allowed={isOwner} need="owner" verb="send orders to suppliers" onClick={send} disabled={act.isPending}>
          Send via WhatsApp
        </GatedButton>
      )}
      {order.status === 'sent' && (
        <>
          <GatedButton allowed={isOwner} need="owner" verb="reopen the WhatsApp message" variant="secondary" onClick={send} disabled={act.isPending}>
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
          <h3 className="text-base font-semibold">{order.supplier_name}</h3>
          <p className="text-xs text-slate-500">
            {lines.length} item{lines.length === 1 ? '' : 's'}
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

      <Modal open={message !== null} title="WhatsApp message" onClose={() => setMessage(null)}>
        <p className="mb-2 text-sm text-slate-600">
          {message?.whatsapp_url ? 'WhatsApp should have opened in a new tab. If not, use the button below or copy the text.' : 'This supplier has no WhatsApp number. Copy the text and send it yourself.'}
        </p>
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm">{message?.whatsapp_text}</pre>
        <div className="mt-3 flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={copy}>Copy message</Button>
          {message?.whatsapp_url && (
            <a href={message.whatsapp_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700">
              Open WhatsApp
            </a>
          )}
        </div>
      </Modal>
    </Card>
  )
}
