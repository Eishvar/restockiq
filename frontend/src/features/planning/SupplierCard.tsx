import { useEffect, useRef, useState } from 'react'
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
import OrderNote from './OrderNote'
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
            className={`rounded-full px-2 py-0.5 ${i < at ? 'bg-emerald-100 text-emerald-800' : i === at ? 'bg-brand-royal text-white' : 'bg-slate-100 text-slate-500'}`}
          >
            {s.label}
          </span>
          {i < steps.length - 1 && <svg aria-hidden="true" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-300"><path d="m9 18 6-6-6-6"/></svg>}
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
  const [saving, setSaving] = useState(false)
  const busyRef = useRef(false)
  useEffect(() => { if (!busyRef.current) setText(String(line.final_packs)) }, [line.final_packs])
  if (!editable) return <span>{line.display_buy}</span>

  async function commit(value = text) {
    const n = Number(value)
    if (!Number.isInteger(n) || n < 0) { setText(String(line.final_packs)); return }
    if (n === line.final_packs) return
    if (busyRef.current) return
    busyRef.current = true
    setSaving(true)
    try {
      await edit.mutateAsync({ orderId: order.id, lineId: line.id, finalPacks: n })
      setText(String(n))
    } catch (err) {
      setText(String(line.final_packs))
      toast(err instanceof Error ? err.message : 'Could not change the amount', 'error')
    } finally {
      busyRef.current = false
      setSaving(false)
    }
  }

  return (
    <div className="flex min-w-40 flex-wrap items-center gap-1">
      <button type="button" aria-label={`Decrease packs of ${line.name}`} disabled={saving || Number(text) <= 0} onPointerDown={(e) => e.preventDefault()} onClick={() => { if (busyRef.current) return; const n = Math.max(0, Number(text || 0) - 1); setText(String(n)); void commit(String(n)) }} className="h-11 w-11 rounded-lg border border-slate-300 bg-white font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40">−</button>
      <input
        type="number"
        min={0}
        step={1}
        inputMode="numeric"
        aria-label={`Packs of ${line.name}`}
        value={text}
        onChange={(e) => { if (/^\d*$/.test(e.target.value)) setText(e.target.value) }}
        onBlur={() => void commit()}
        onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
        disabled={saving}
        className={`${inputCls} h-11 w-16 text-center`}
      />
      <span className="text-xs text-slate-500">{line.pack_uom}</span>
      <button type="button" aria-label={`Increase packs of ${line.name}`} disabled={saving} onPointerDown={(e) => e.preventDefault()} onClick={() => { if (busyRef.current) return; const n = Math.max(0, Number(text || 0)) + 1; setText(String(n)); void commit(String(n)) }} className="h-11 w-11 rounded-lg border border-slate-300 bg-white font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40">+</button>
      {saving && <span role="status" className="text-xs text-slate-500">Saving…</span>}
      {line.final_packs !== line.suggested_packs && <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-1 text-xs text-amber-900">Edited (suggested: {line.suggested_packs}) <button type="button" aria-label={`Reset packs of ${line.name} to suggested ${line.suggested_packs}`} disabled={saving} className="min-h-11 font-semibold underline" onPointerDown={(e) => e.preventDefault()} onClick={() => { if (busyRef.current) return; setText(String(line.suggested_packs)); void commit(String(line.suggested_packs)) }}>Reset</button></span>}
    </div>
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
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-gradient-to-r from-brand-royal/10 via-brand-sky/10 to-brand-cyan/10 p-3">
        <div className="flex min-w-0 items-center gap-3">
          {showSupplierTitle && <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-royal text-lg font-bold text-white">{order.supplier_name.trim().charAt(0).toUpperCase()}</span>}
          <div className="min-w-0">
            {showSupplierTitle ? (
              <h3 className="truncate text-base font-semibold text-brand-navy">{order.supplier_name}</h3>
            ) : (
              <h3 className="text-sm font-semibold text-brand-navy">Order #{order.id}</h3>
            )}
            <p className="text-xs text-slate-600">
              {!showSupplierTitle && `Plan #${order.run_id} (${order.plan_today}) · `}
              {lines.length} item{lines.length === 1 ? '' : 's'}
              {order.created_at ? ` · created ${fmtDay(order.created_at.slice(0, 10))}` : ''}
              {order.approved_by_name ? ` · approved by ${order.approved_by_name}` : ''}
            </p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">Order total</div>
          <div className="text-xl font-bold tabular-nums text-brand-royal">{rm(order.total_rm)}</div>
        </div>
      </div>
      <div className="mt-3">
        <Stepper status={order.status} />
        {order.status === 'rejected' && order.reject_reason && (
          <p className="mt-1 text-sm text-red-700">Reason: {order.reject_reason}</p>
        )}
      </div>
      {order.warnings.map((w) => (
        <p key={w} className="mt-2 flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900"><svg aria-hidden="true" className="mt-0.5 shrink-0" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3 2.7 20h18.6L12 3Z"/><path d="M12 9v5m0 3h.01"/></svg>{w}</p>
      ))}
      {order.plan_is_stale && (
        <p role="alert" className="mt-2 flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <svg aria-hidden="true" className="mt-0.5 shrink-0" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3 2.7 20h18.6L12 3Z"/><path d="M12 9v5m0 3h.01"/></svg>
          Your sales data changed after this plan was made. Generate a new plan before you approve this order, so it uses the latest numbers.
        </p>
      )}

      <div className="mt-3 space-y-2">
        {lines.map((l) => {
          const edited = l.final_packs !== l.suggested_packs
          return (
          <section key={l.id} className={`rounded-xl border border-l-4 bg-white p-3 sm:p-4 ${edited ? 'border-amber-200 border-l-amber-400' : 'border-slate-200 border-l-emerald-400'}`} aria-label={`${l.name} order line`}>
            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
              <div className="min-w-0">
                <h4 className="font-semibold text-slate-900">{l.name}</h4>
                <div className="mt-2 inline-flex flex-wrap items-center gap-2 rounded-lg bg-brand-surface px-2.5 py-1.5">
                  <span className="text-xs font-semibold uppercase tracking-wide text-brand-navy">Buy</span>
                  <Buy line={l} order={order} editable={editable} />
                </div>
              </div>
              <div className="flex items-baseline justify-between gap-4 border-t border-slate-100 pt-2 sm:block sm:border-0 sm:pt-0 sm:text-right">
                <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Cost</span>
                <span className="text-lg font-bold tabular-nums text-brand-navy sm:block">{rm(l.line_total_rm)}</span>
              </div>
            </div>
            <details className="mt-2 border-t border-slate-100 pt-1">
              <summary className="flex min-h-9 w-fit cursor-pointer items-center rounded text-sm font-medium text-brand-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-royal">
                Planning details
              </summary>
              <dl className="mt-2 grid grid-cols-2 gap-x-5 gap-y-3 rounded-lg bg-brand-surface/60 p-3 text-sm lg:grid-cols-3">
                <div><dt className="text-xs text-slate-500">Forecast need</dt><dd className="mt-0.5 font-medium">{l.display_need}</dd></div>
                <div><dt className="text-xs text-slate-500">Safety buffer</dt><dd className="mt-0.5 font-medium"><Buffer line={l} /></dd></div>
                <div><dt className="text-xs text-slate-500">Usable stock</dt><dd className="mt-0.5 font-medium"><Stock line={l} /></dd></div>
                <div><dt className="text-xs text-slate-500">Buy schedule</dt><dd className="mt-0.5"><When line={l} /></dd></div>
                <div><dt className="text-xs text-slate-500">Pack price</dt><dd className="mt-0.5 font-medium tabular-nums">{rm(l.pack_price_rm)}</dd></div>
              </dl>
            </details>
            <Button variant="ghost" className="px-0" onClick={() => setOpen(open === l.id ? null : l.id)} aria-expanded={open === l.id} aria-controls={`why-${order.id}-${l.id}`}>
              Why?
            </Button>
            {open === l.id && <div id={`why-${order.id}-${l.id}`} className="mt-1"><Why line={l} /></div>}
          </section>
          )
        })}
      </div>

      {order.note_text && <OrderNote text={order.note_text} />}

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
            <a href={message.whatsapp_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center rounded-lg bg-brand-royal px-4 py-2 text-sm font-medium text-white hover:bg-brand-hover">
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
