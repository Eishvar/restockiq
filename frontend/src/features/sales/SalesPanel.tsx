import { useMemo, useRef, useState } from 'react'
import { Badge, Button, Card, EmptyState, Modal, PageSkeleton, Table, useToast } from '../../components/ui'
import { inputCls } from '../inventory/QtyInput'
import { fmtDayYear, rm } from '../planning/format'
import { useRole } from '../planning/GatedButton'
import { useRecipeBook } from '../recipes/api'
import {
  downloadTemplate, useConfirmImport, useDeleteForever, usePreviewFile, useRemovePreview, useRemoveSales, useRestoreSales,
  useSalesOverview,
  type ConfirmBody, type ImportPreview, type RemoveTarget, type RemovedRecord, type RowEdit, type SalesOverview,
} from './api'

const KIND: Record<string, string> = { csv: 'CSV', xlsx: 'Excel', pdf: 'PDF' }
const ACCEPT = '.csv,.xlsx,.pdf,text/csv,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
const day = (iso: string) => fmtDayYear(iso)
const range = (a: string, b: string) => (a === b ? day(a) : `${day(a)} to ${day(b)}`)
const when = (iso: string) => fmtDayYear(iso.slice(0, 10))

function CoverageCard({ o }: { o: SalesOverview }) {
  const c = o.coverage
  return (
    <Card title="Sales in RestockAI">
      {c.first_date && c.last_date ? (
        <div className="grid gap-3 sm:grid-cols-3">
          <div><div className="text-xs text-slate-500">Covers</div><div className="font-medium">{range(c.first_date, c.last_date)}</div></div>
          <div><div className="text-xs text-slate-500">Days of sales</div><div className="font-medium">{c.days.toLocaleString()}</div></div>
          <div>
            <div className="text-xs text-slate-500">Today in the app{o.today_is_demo_date ? ' (demo date)' : ''}</div>
            <div className="font-medium">{day(o.today)}</div>
          </div>
        </div>
      ) : (
        <p className="text-sm text-slate-600">There are no sales yet. Upload a sales report to start.</p>
      )}
      <p className="mt-3 text-xs text-slate-500">
        &quot;Today&quot; is the day after your latest sales, so adding a day of sales moves it forward. The forecast learns from these sales.
      </p>
    </Card>
  )
}

function UploadCard({ o, canEdit, pending, onFile }: { o: SalesOverview; canEdit: boolean; pending: boolean; onFile: (f: File) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const toast = useToast()
  if (!canEdit) {
    return <Card title="Add sales"><p className="text-sm text-slate-600">Managers and the owner can add or remove sales.</p></Card>
  }
  return (
    <Card title="Add sales from a file">
      <p className="mb-3 text-sm text-slate-600">
        Upload the sales report from your till as a <strong>CSV</strong>, <strong>Excel</strong> or <strong>PDF</strong> file. You will see what was
        read and can fix it before anything is saved.
        {' '}A PDF is read by AI, so check its numbers carefully.
      </p>
      <div
        onDragOver={(e) => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) onFile(f) }}
        className={`rounded-xl border-2 border-dashed p-6 text-center ${over ? 'border-brand-royal bg-brand-surface' : 'border-slate-300'}`}
      >
        <p className="text-sm text-slate-700">{pending ? 'Reading your file…' : 'Drag a file here, or'}</p>
        <div className="mt-2 flex flex-wrap justify-center gap-2">
          <Button onClick={() => input.current?.click()} disabled={pending}>{pending ? 'Reading…' : 'Choose a file'}</Button>
          <Button variant="secondary" onClick={() => downloadTemplate().catch(() => toast('Could not download the template', 'error'))}>Download a CSV template</Button>
        </div>
        <input ref={input} type="file" accept={ACCEPT} className="hidden" aria-label="Sales file"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = '' }} />
      </div>
      {!o.ai_available && <p className="mt-2 text-xs text-slate-500">PDF files cannot be read right now (the AI service is not set up). CSV and Excel work.</p>}
      <p className="mt-2 text-xs text-slate-500">
        The file needs these columns: Date, Item Code or Item Name, and Qty Sold (Net Sales is optional). Dishes that are not on your menu are listed and left out
        until you match them. A day in the file replaces that day&apos;s sales; what it replaces is kept aside, so you can restore it.
      </p>
    </Card>
  )
}

type Edit = { date?: string; item_id?: number | null; qty?: string; net?: string }

function PreviewCard({ preview, onDone, onCancel }: { preview: ImportPreview; onDone: () => void; onCancel: () => void }) {
  const confirm = useConfirmImport()
  const book = useRecipeBook()
  const toast = useToast()
  const [edits, setEdits] = useState<Record<number, Edit>>({})
  const [dropped, setDropped] = useState<Record<number, boolean>>({})
  const [dishMap, setDishMap] = useState<Record<string, number | ''>>({})
  const [error, setError] = useState('')
  const dishes = useMemo(() => [...(book.data ?? [])].sort((a, b) => a.name.localeCompare(b.name)), [book.data])
  const setEdit = (i: number, change: Edit) => setEdits((e) => ({ ...e, [i]: { ...e[i], ...change } }))

  const mapped = (dish: string) => (dishMap[dish] === undefined || dishMap[dish] === '' ? null : Number(dishMap[dish]))

  async function save() {
    setError('')
    const body: ConfirmBody = { draft_id: preview.draft_id, edits: [], dish_map: {} }
    for (const [dish, id] of Object.entries(dishMap)) if (id !== '') body.dish_map[dish] = Number(id)
    for (const r of preview.rows) {
      if (dropped[r.i]) { body.edits.push({ i: r.i, drop: true }); continue }
      const e = edits[r.i]
      if (!e) continue
      const out: RowEdit = { i: r.i }
      if (e.date !== undefined) out.date = e.date
      if (e.item_id != null) out.item_id = e.item_id
      if (e.qty !== undefined && e.qty !== '') out.qty = Number(e.qty)
      if (e.net !== undefined && e.net !== '') out.net = Number(e.net)
      body.edits.push(out)
    }
    try {
      const r = await confirm.mutateAsync(body)
      toast(
        `Saved ${r.rows_saved} row${r.rows_saved === 1 ? '' : 's'} for ${r.days} day${r.days === 1 ? '' : 's'} (${r.new_days} new, ${r.replaced_days} replaced). ` +
          `Today is now ${day(r.today)}.` + (r.rows_left_out ? ` ${r.rows_left_out} row${r.rows_left_out === 1 ? ' was' : 's were'} left out.` : ''),
        'success',
      )
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the sales')
    }
  }

  return (
    <Card title={`Check ${preview.filename}`}>
      {preview.read_by_ai && (
        <div className="mb-3 rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900">
          <strong>Read by AI from a PDF.</strong> AI can misread a number, so look through the rows below and fix anything wrong before you save.
          {preview.notes && <p className="mt-1">The AI&apos;s remark: {preview.notes}</p>}
        </div>
      )}
      <dl className="grid gap-3 text-sm sm:grid-cols-4">
        <div><dt className="text-xs text-slate-500">Rows that can be saved</dt><dd className="font-medium">{preview.rows_ok} of {preview.rows_total}</dd></div>
        <div><dt className="text-xs text-slate-500">Days</dt><dd className="font-medium">{preview.date_from && preview.date_to ? range(preview.date_from, preview.date_to) : '—'} ({preview.days})</dd></div>
        <div><dt className="text-xs text-slate-500">New days / replaced days</dt><dd className="font-medium">{preview.new_days} / {preview.replaced_days}</dd></div>
        <div><dt className="text-xs text-slate-500">Dishes sold · sales</dt><dd className="font-medium">{preview.dishes_sold.toLocaleString()} · {rm(preview.net_sales_rm)}</dd></div>
      </dl>

      {preview.unmatched.length > 0 && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
          <p className="text-sm font-medium text-amber-900">These dishes are not on your menu. Match each one, or leave its rows out.</p>
          <ul className="mt-2 space-y-2">
            {preview.unmatched.map((u) => (
              <li key={u.dish} className="flex flex-wrap items-center gap-2 text-sm">
                <span className="min-w-0 flex-1 basis-48">&ldquo;{u.dish}&rdquo; <span className="text-slate-500">({u.rows} row{u.rows === 1 ? '' : 's'})</span></span>
                <select aria-label={`Match ${u.dish} to a dish`} value={dishMap[u.dish] ?? ''} onChange={(e) => setDishMap((m) => ({ ...m, [u.dish]: e.target.value ? Number(e.target.value) : '' }))} className={`${inputCls} w-60 max-w-full`}>
                  <option value="">Leave these rows out</option>
                  {dishes.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
            <tr><th className="px-2 py-2">Date</th><th className="px-2 py-2">Dish</th><th className="px-2 py-2">Qty</th><th className="px-2 py-2">Amount (RM)</th><th className="px-2 py-2">Check</th><th className="px-2 py-2">Leave out</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {preview.rows.map((r) => {
              const e = edits[r.i] ?? {}
              const item = e.item_id !== undefined ? e.item_id : mapped(r.dish) ?? r.item_id
              const touched = e.date !== undefined || e.item_id !== undefined || e.qty !== undefined || e.net !== undefined || mapped(r.dish) !== null
              const out = !!dropped[r.i]
              return (
                <tr key={r.i} className={out ? 'bg-slate-50 opacity-50' : r.problem && !touched ? 'bg-red-50/50' : ''}>
                  <td className="px-2 py-1.5">
                    <input type="date" aria-label="Date" value={e.date ?? r.date ?? ''} title={r.date ? undefined : `Written as "${r.date_text}"`}
                      onChange={(ev) => setEdit(r.i, { date: ev.target.value })} className={inputCls} />
                  </td>
                  <td className="px-2 py-1.5">
                    <select aria-label="Dish" value={item ?? ''} onChange={(ev) => setEdit(r.i, { item_id: ev.target.value ? Number(ev.target.value) : null })} className={`${inputCls} w-52 max-w-full`}>
                      <option value="">{r.dish} (not matched)</option>
                      {dishes.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                    </select>
                  </td>
                  <td className="px-2 py-1.5">
                    <input type="number" min={0} aria-label="Quantity" value={e.qty ?? (r.qty ?? '')} onChange={(ev) => setEdit(r.i, { qty: ev.target.value })} className={`${inputCls} w-20`} />
                  </td>
                  <td className="px-2 py-1.5">
                    <input type="number" min={0} step="0.01" aria-label="Amount" placeholder="menu price" value={e.net ?? (r.net ?? '')} onChange={(ev) => setEdit(r.i, { net: ev.target.value })} className={`${inputCls} w-24`} />
                  </td>
                  <td className="px-2 py-1.5 text-xs">
                    {r.problem && !touched ? <span className="text-red-700">{r.problem}</span> : touched ? <Badge tone="good">changed</Badge> : <span className="text-slate-400">ok</span>}
                  </td>
                  <td className="px-2 py-1.5"><input type="checkbox" aria-label="Leave this row out" checked={out} onChange={(ev) => setDropped((d) => ({ ...d, [r.i]: ev.target.checked }))} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {preview.rows_shown < preview.rows_total && (
        <p className="mt-2 text-xs text-slate-500">
          Showing {preview.rows_shown} of {preview.rows_total} rows, with the ones that need a look first. Every row that is fine is saved when you confirm.
        </p>
      )}
      {error && <p role="alert" className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <Button variant="secondary" onClick={onCancel} disabled={confirm.isPending}>Cancel</Button>
        <Button onClick={save} disabled={confirm.isPending}>{confirm.isPending ? 'Saving…' : 'Save these sales'}</Button>
      </div>
    </Card>
  )
}

function RemoveModal({ target, onClose }: { target: RemoveTarget | null; onClose: () => void }) {
  const preview = useRemovePreview(target)
  const remove = useRemoveSales()
  const toast = useToast()
  const p = preview.data

  async function go() {
    if (!target) return
    try {
      const r = await remove.mutateAsync(target)
      toast(`Removed ${r.removal.label}. You can restore it under "Recently removed". Today is now ${day(r.today)}.`, 'success')
      onClose()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not remove', 'error')
    }
  }

  return (
    <Modal open={target !== null} title="Remove sales?" onClose={onClose}>
      {preview.isLoading && <p className="text-sm text-slate-500">Checking…</p>}
      {preview.error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{preview.error.message}</p>}
      {p && (
        <div className="space-y-2 text-sm text-slate-700">
          <p><strong>{p.label}</strong>: {p.days} day{p.days === 1 ? '' : 's'}, {p.rows} row{p.rows === 1 ? '' : 's'} ({range(p.date_from, p.date_to)}).</p>
          <p>They stop counting for forecasts and plans straight away. They are kept aside, so you can restore them if this was a mistake.</p>
          {p.today_after && p.today_after !== p.today_now && (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">
              Today in the app moves from <strong>{day(p.today_now)}</strong> back to <strong>{day(p.today_after)}</strong>, because today is the day after your latest sales.
            </p>
          )}
          <p>Plans made before this will show a warning to generate a new one.</p>
        </div>
      )}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose} disabled={remove.isPending}>Cancel</Button>
        <Button variant="danger" onClick={go} disabled={!p || remove.isPending}>{remove.isPending ? 'Removing…' : 'Remove these sales'}</Button>
      </div>
    </Modal>
  )
}

function HistoryCard({ o, canEdit, onRemove }: { o: SalesOverview; canEdit: boolean; onRemove: (t: RemoveTarget) => void }) {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  return (
    <Card title="Files you have added">
      {o.imports.length === 0 ? (
        <p className="text-sm text-slate-600">No files yet. The sales that came with the demo are not listed here; remove them by dates below.</p>
      ) : (
        <Table head={['File', 'Days', 'When', 'Added by', 'Status', '']}>
          {o.imports.map((i) => (
            <tr key={i.id}>
              <td className="font-medium">{i.filename} <Badge>{KIND[i.kind] ?? i.kind}</Badge>{i.read_by_ai && <> <Badge tone="warn">read by AI</Badge></>}</td>
              <td>{range(i.date_from, i.date_to)} <span className="text-slate-500">({i.days})</span></td>
              <td>{when(i.ts)}</td>
              <td>{i.user_name ?? '—'}</td>
              <td>{i.status === 'active' ? <Badge tone="good">in use</Badge> : <Badge>removed</Badge>}</td>
              <td className="text-right">{i.status === 'active' && canEdit && <Button variant="secondary" onClick={() => onRemove({ import_id: i.id })}>Remove</Button>}</td>
            </tr>
          ))}
        </Table>
      )}
      {canEdit && (
        <div className="mt-4 border-t border-slate-100 pt-3">
          <p className="mb-2 text-sm font-medium">Remove sales for certain days</p>
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-sm"><span className="mb-1 block text-xs text-slate-500">From</span><input type="date" value={from} onChange={(e) => { setFrom(e.target.value); if (!to || to < e.target.value) setTo(e.target.value) }} className={inputCls} /></label>
            <label className="text-sm"><span className="mb-1 block text-xs text-slate-500">To</span><input type="date" min={from} value={to} onChange={(e) => setTo(e.target.value)} className={inputCls} /></label>
            <Button variant="secondary" disabled={!from || !to} onClick={() => onRemove({ date_from: from, date_to: to })}>Review removal</Button>
          </div>
        </div>
      )}
    </Card>
  )
}

function RemovedCard({ items, canEdit, isOwner }: { items: RemovedRecord[]; canEdit: boolean; isOwner: boolean }) {
  const restore = useRestoreSales()
  const purge = useDeleteForever()
  const toast = useToast()
  const [purging, setPurging] = useState<RemovedRecord | null>(null)

  async function put(r: RemovedRecord) {
    try {
      const res = await restore.mutateAsync(r.id)
      toast(`Restored ${res.removal.label}. Today is now ${day(res.today)}.`, 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not restore', 'error')
    }
  }

  async function erase() {
    if (!purging) return
    try {
      await purge.mutateAsync(purging.id)
      toast('Deleted for good', 'success')
      setPurging(null)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not delete', 'error')
    }
  }

  return (
    <Card title="Recently removed">
      {items.length === 0 ? (
        <p className="text-sm text-slate-600">Nothing has been removed. Sales you remove, or that a new file replaces, wait here so you can restore them.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {items.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
              <div className="min-w-0 flex-1 basis-60">
                <div className="font-medium">{r.label}</div>
                <div className="text-xs text-slate-500">{range(r.date_from, r.date_to)} · {r.days} day{r.days === 1 ? '' : 's'} · {r.rows} rows · removed {when(r.ts)}{r.user_name ? ` by ${r.user_name}` : ''}</div>
              </div>
              {canEdit && <Button variant="secondary" onClick={() => put(r)} disabled={restore.isPending}>Restore</Button>}
              {isOwner && <Button variant="danger" onClick={() => setPurging(r)}>Delete forever</Button>}
            </li>
          ))}
        </ul>
      )}
      <Modal open={purging !== null} title="Delete these sales forever?" onClose={() => setPurging(null)}>
        <p className="text-sm text-slate-700">{purging?.label} ({purging?.rows} rows) will be erased and <strong>cannot be restored</strong>.</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setPurging(null)} disabled={purge.isPending}>Cancel</Button>
          <Button variant="danger" onClick={erase} disabled={purge.isPending}>{purge.isPending ? 'Deleting…' : 'Delete forever'}</Button>
        </div>
      </Modal>
    </Card>
  )
}

/** Sales data in one place: what is loaded, add a file, check it, and take wrong data back out. */
export default function SalesPanel({ mode }: { mode: 'page' | 'setup' }) {
  const overview = useSalesOverview()
  const upload = usePreviewFile()
  const { isManager, isOwner } = useRole()
  const toast = useToast()
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [removing, setRemoving] = useState<RemoveTarget | null>(null)

  if (overview.isLoading) return <PageSkeleton rows={2} />
  if (overview.error || !overview.data) return <EmptyState title="Could not load the sales data" hint={overview.error?.message} />
  const o = overview.data

  async function onFile(file: File) {
    try {
      setPreview(await upload.mutateAsync(file))
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not read the file', 'error')
    }
  }

  return (
    <div className="space-y-4">
      <CoverageCard o={o} />
      <UploadCard o={o} canEdit={isManager} pending={upload.isPending} onFile={onFile} />
      {preview && <PreviewCard key={preview.draft_id} preview={preview} onDone={() => setPreview(null)} onCancel={() => setPreview(null)} />}
      {mode === 'page' && (
        <>
          <HistoryCard o={o} canEdit={isManager} onRemove={setRemoving} />
          <RemovedCard items={o.removed} canEdit={isManager} isOwner={isOwner} />
          <RemoveModal target={removing} onClose={() => setRemoving(null)} />
        </>
      )}
    </div>
  )
}
