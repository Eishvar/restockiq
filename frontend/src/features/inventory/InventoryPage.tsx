import { useState } from 'react'
import { Button, Card, ConfirmModal, EmptyState, PageSkeleton, SegmentedControl, Table, Tooltip, useToast } from '../../components/ui'
import { useMe } from '../auth/api'
import {
  useDiscardBatch,
  useDiscardExpired,
  useInventory,
  usePatchBatch,
  useRemoveBatch,
  useRemoveItem,
  type Batch,
  type BatchPatch,
  type InventoryRow,
  type Status,
} from './api'
import QuickNoteModal from '../assistant/QuickNoteModal'
import AddBatchModal from './AddBatchModal'
import AddItemModal from './AddItemModal'
import HistoryModal from './HistoryModal'
import OnboardingWizard from './OnboardingWizard'
import QtyInput, { inputCls } from './QtyInput'
import { StatusBadge, STORAGE_LABEL, fmtDate } from './shared'

type Filter = 'all' | Status

const rm = (n: number) => `RM ${n.toLocaleString('en-MY', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

/** One batch: a purchase of this item on one day, with its own shelf life, price and expiry date. */
function BatchRowView({ item, batch, today, canEditAll }: { item: InventoryRow; batch: Batch; today: string; canEditAll: boolean }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<BatchPatch>({})
  const patch = usePatchBatch()
  const remove = useRemoveBatch()
  const discard = useDiscardBatch()
  const toast = useToast()
  const [confirmAction, setConfirmAction] = useState<'discard' | 'delete' | null>(null)
  const [confirmError, setConfirmError] = useState('')
  const fail = (err: unknown) => toast(err instanceof Error ? err.message : 'Something went wrong', 'error')
  const expired = batch.status === 'expired'
  const label = `${item.name} bought ${fmtDate(batch.procured_on)}`

  async function save() {
    try {
      if (Object.keys(draft).length) await patch.mutateAsync({ id: batch.id, patch: draft })
      toast(`${label} updated`, 'success')
      setEditing(false)
      setDraft({})
    } catch (err) {
      fail(err)
    }
  }

  async function onDiscard() {
    try {
      await discard.mutateAsync(batch.id)
      toast(`Expired ${item.name} removed`, 'success')
      setConfirmAction(null)
    } catch (err) {
      setConfirmError(err instanceof Error ? err.message : 'Could not remove expired stock')
    }
  }

  async function onRemove() {
    try {
      await remove.mutateAsync(batch.id)
      toast('Batch deleted', 'success')
      setConfirmAction(null)
    } catch (err) {
      setConfirmError(err instanceof Error ? err.message : 'Could not delete this batch')
    }
  }

  const editAll = editing && canEditAll
  return (
    <tr className={expired ? 'bg-red-50' : ''}>
      <td className="pl-8 whitespace-nowrap">
        {editAll ? (
          <input
            type="date"
            aria-label="Bought on"
            max={today}
            value={draft.procured_on ?? batch.procured_on}
            onChange={(e) => e.target.value && setDraft((d) => ({ ...d, procured_on: e.target.value }))}
            className={inputCls}
          />
        ) : (
          <span className="text-slate-700">Bought {fmtDate(batch.procured_on)}</span>
        )}
      </td>
      <td className="whitespace-nowrap">
        {editing ? (
          <QtyInput baseQty={draft.qty_base ?? batch.qty_base} item={item} onChange={(q) => setDraft((d) => ({ ...d, qty_base: q }))} />
        ) : (
          batch.display_qty
        )}
      </td>
      <td className="whitespace-nowrap">
        {editAll ? (
          <input
            type="number"
            min={0}
            step="0.01"
            aria-label="Price per pack"
            value={draft.pack_price_rm ?? batch.pack_price_rm}
            onChange={(e) => e.target.value !== '' && setDraft((d) => ({ ...d, pack_price_rm: parseFloat(e.target.value) }))}
            className={`${inputCls} w-24`}
          />
        ) : (
          `${rm(batch.pack_price_rm)} / pack`
        )}
      </td>
      <td className="whitespace-nowrap">{rm(batch.value_rm)}</td>
      <td className="whitespace-nowrap">
        {editAll ? (
          <input
            type="number"
            min={1}
            aria-label="Shelf life in days"
            value={draft.shelf_life_days ?? batch.shelf_life_days}
            onChange={(e) => e.target.value && setDraft((d) => ({ ...d, shelf_life_days: parseInt(e.target.value) }))}
            className={`${inputCls} w-20`}
          />
        ) : (
          `${batch.shelf_life_days} days`
        )}
      </td>
      <td className="whitespace-nowrap">{fmtDate(batch.expires_on)}</td>
      <td>
        <StatusBadge row={batch} />
      </td>
      <td className="whitespace-nowrap text-right">
        <div className="flex justify-end gap-1">
          {editing ? (
            <>
              <Button onClick={save} disabled={patch.isPending}>
                Save
              </Button>
              <Button variant="secondary" onClick={() => { setEditing(false); setDraft({}) }}>
                Cancel
              </Button>
            </>
          ) : (
            <>
              {expired && (
                  <Button variant="danger" onClick={() => { setConfirmAction('discard'); setConfirmError('') }} disabled={discard.isPending}>
                  Remove expired
                </Button>
              )}
              <Button variant="ghost" onClick={() => setEditing(true)}>
                Edit
              </Button>
              {canEditAll && !expired && (
                <Button variant="ghost" onClick={() => { setConfirmAction('delete'); setConfirmError('') }} disabled={remove.isPending}>
                  Delete
                </Button>
              )}
            </>
          )}
        </div>
      </td>
      <ConfirmModal open={!!confirmAction} title={confirmAction === 'discard' ? 'Remove expired stock?' : 'Delete stock batch?'} description={confirmAction === 'discard' ? `Remove the expired ${item.name} (${batch.display_qty}) bought ${fmtDate(batch.procured_on)} from your stock?` : `Delete this batch of ${item.name} bought ${fmtDate(batch.procured_on)}? Its history is kept.`} pending={discard.isPending || remove.isPending} error={confirmError} onCancel={() => { setConfirmAction(null); setConfirmError('') }} onConfirm={() => void (confirmAction === 'discard' ? onDiscard() : onRemove())} />
    </tr>
  )
}

/** An item and all its batches, kept separate so each shows its own expiry date. */
function ItemGroup({
  row, today, canEditAll, onHistory, onAddBatch,
}: { row: InventoryRow; today: string; canEditAll: boolean; onHistory: () => void; onAddBatch: () => void }) {
  const remove = useRemoveItem()
  const toast = useToast()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmError, setConfirmError] = useState('')

  async function onRemove() {
    try {
      await remove.mutateAsync(row.ingredient_id)
      toast(`${row.name} removed`, 'success')
      setConfirmOpen(false)
    } catch (err) {
      setConfirmError(err instanceof Error ? err.message : 'Could not remove this item')
    }
  }

  const manager = (label: string, button: React.ReactNode) =>
    canEditAll ? button : <Tooltip text={`Only managers and owners can ${label}`}>{button}</Tooltip>

  return (
    <>
      <tr className="bg-slate-50">
        <td colSpan={3}>
          <div className="font-semibold">{row.name}</div>
          <div className="text-xs text-slate-500">
            {STORAGE_LABEL[row.storage]}
            {row.supplier_name ? ` · ${row.supplier_name}` : ''}
            {row.batches.length > 1 ? ` · ${row.batches.length} batches` : ''}
          </div>
        </td>
        <td className="whitespace-nowrap font-medium">
          {row.display_qty} · {rm(row.stock_value_rm)}
        </td>
        <td colSpan={2} />
        <td>{row.batches.length > 0 && <StatusBadge row={row} />}</td>
        <td className="whitespace-nowrap text-right">
          <div className="flex justify-end gap-1">
            {manager('add stock', <Button variant="secondary" onClick={onAddBatch} disabled={!canEditAll}>+ Add stock</Button>)}
            <Button variant="ghost" onClick={onHistory}>
              History
            </Button>
            {manager('remove items', <Button variant="ghost" title="Remove this item and all its batches" onClick={() => { setConfirmOpen(true); setConfirmError('') }} disabled={!canEditAll}>Remove</Button>)}
          </div>
        </td>
      </tr>
      {row.batches.length === 0 ? (
        <tr>
          <td colSpan={8} className="pl-8 text-slate-500">
            None in stock.
          </td>
        </tr>
      ) : (
        row.batches.map((b) => <BatchRowView key={b.id} item={row} batch={b} today={today} canEditAll={canEditAll} />)
      )}
      <ConfirmModal open={confirmOpen} title="Remove this item?" description={`Remove ${row.name} and all its batches from your stock? Its history is kept.`} pending={remove.isPending} error={confirmError} onCancel={() => { setConfirmOpen(false); setConfirmError('') }} onConfirm={() => void onRemove()} />
    </>
  )
}

export default function InventoryPage() {
  const { data, isLoading, error, refetch } = useInventory()
  const me = useMe()
  const discard = useDiscardExpired()
  const toast = useToast()
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [storage, setStorage] = useState('')
  const [adding, setAdding] = useState(false)
  const [noting, setNoting] = useState(false)
  const [history, setHistory] = useState<InventoryRow | null>(null)
  const [batchFor, setBatchFor] = useState<InventoryRow | null>(null)
  const [confirmDiscardAll, setConfirmDiscardAll] = useState(false)
  const [discardAllError, setDiscardAllError] = useState('')

  if (isLoading) return <PageSkeleton rows={4} />
  if (error || !data) return <EmptyState title="Could not load your stock" hint={error?.message ?? 'Please try again.'} action={<button type="button" onClick={() => void refetch()} className="text-sm font-semibold text-emerald-800 underline">Try again</button>} />

  const role = me.data?.role
  const canEditAll = role === 'owner' || role === 'manager'

  // The owner sets up stock once; everyone else sees the normal page with a short note.
  if (!data.onboarded && role === 'owner') return <OnboardingWizard data={data} />

  const expiredBatches = data.items.flatMap((i) => i.batches.filter((b) => b.status === 'expired').map((b) => ({ item: i, batch: b })))
  const soonBatches = data.items.flatMap((i) => i.batches.filter((b) => b.status === 'expiring_soon').map((b) => ({ item: i, batch: b })))
  const rows = data.items.filter(
    (i) =>
      (filter === 'all' || i.status === filter) &&
      (!storage || i.storage === storage) &&
      i.name.toLowerCase().includes(query.trim().toLowerCase()),
  )

  async function discardAll() {
    try {
      const r = await discard.mutateAsync(null)
      toast(`${r.batches} expired batch${r.batches === 1 ? '' : 'es'} removed`, 'success')
      setConfirmDiscardAll(false)
    } catch (err) {
      setDiscardAllError(err instanceof Error ? err.message : 'Could not discard expired stock')
    }
  }

  const addButton = (
    <Button onClick={() => setAdding(true)} disabled={!canEditAll}>
      + Add item
    </Button>
  )

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Inventory</h1>
          <p className="text-sm text-slate-600">
            What you have now, as of {fmtDate(data.today)}. The same item bought on different days is kept as separate batches.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => setNoting(true)} className="rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-900 hover:bg-emerald-100">
            Quick add from a note <span className="mt-0.5 block text-left text-xs font-normal text-emerald-800">English or Bahasa Malaysia · “beras 12 bag, telur 3 tray…”</span>
          </button>
          {canEditAll ? addButton : <Tooltip text="Only managers and owners can add items">{addButton}</Tooltip>}
        </div>
      </div>

      {!data.onboarded && (
        <div className="rounded-xl border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900">
          The owner has not confirmed the opening stock yet. These numbers are an example until they do.
        </div>
      )}

      {expiredBatches.length > 0 && (
        <div className="rounded-xl border border-red-300 bg-red-50 p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm font-semibold text-red-900">Expired ({expiredBatches.length}) – not counted as stock</div>
            <Button variant="danger" onClick={() => { setConfirmDiscardAll(true); setDiscardAllError('') }} disabled={discard.isPending}>
              Remove all expired
            </Button>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {expiredBatches.map(({ item, batch }) => (
              <div key={batch.id} className="flex items-center justify-between gap-2 rounded-lg border border-red-200 bg-white px-3 py-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-slate-900">{item.name}</div>
                  <div className="text-xs text-slate-500">Bought {fmtDate(batch.procured_on)} · {batch.display_qty}</div>
                </div>
                <span className="shrink-0 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">Expired</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {soonBatches.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
          <div className="mb-2 text-sm font-semibold text-amber-900">Use soon ({soonBatches.length})</div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {soonBatches.map(({ item, batch }) => (
              <div key={batch.id} className="flex items-center justify-between gap-2 rounded-lg border border-amber-200 bg-white px-3 py-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-slate-900">{item.name}</div>
                  <div className="text-xs text-slate-500">Bought {fmtDate(batch.procured_on)}</div>
                </div>
                <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
                  {batch.days_left} day{batch.days_left === 1 ? '' : 's'} left
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <input
            type="search"
            aria-label="Search items"
            placeholder="Search items"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className={`${inputCls} w-48`}
          />
          <SegmentedControl<Filter>
            label="Filter by status"
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'all', label: 'All' },
              { value: 'ok', label: 'OK' },
              { value: 'expiring_soon', label: 'Expiring soon' },
              { value: 'expired', label: 'Expired' },
            ]}
          />
          <select aria-label="Filter by storage" value={storage} onChange={(e) => setStorage(e.target.value)} className={inputCls}>
            <option value="">All storage</option>
            <option value="freezer">Freezer</option>
            <option value="chiller">Chiller</option>
            <option value="dry">Dry store</option>
          </select>
        </div>

        {rows.length === 0 ? (
          <EmptyState title="No items match" hint="Try a different search or filter." />
        ) : (
          <Table head={['Item / batch', 'In stock', 'Price', 'Value', 'Good for', 'Expires', 'Status', '']}>
            {rows.map((r) => (
              <ItemGroup
                key={r.ingredient_id}
                row={r}
                today={data.today}
                canEditAll={canEditAll}
                onHistory={() => setHistory(r)}
                onAddBatch={() => setBatchFor(r)}
              />
            ))}
          </Table>
        )}
      </Card>

      <AddBatchModal item={batchFor} today={data.today} onClose={() => setBatchFor(null)} />
      <AddItemModal open={adding} today={data.today} onClose={() => setAdding(false)} />
      <QuickNoteModal open={noting} data={data} onClose={() => setNoting(false)} />
      <HistoryModal ingredientId={history?.ingredient_id ?? null} name={history?.name ?? ''} onClose={() => setHistory(null)} />
      <ConfirmModal open={confirmDiscardAll} title="Remove all expired batches?" description={`Remove all ${expiredBatches.length} expired batches from your stock? This does not remove their history.`} pending={discard.isPending} error={discardAllError} onCancel={() => { setConfirmDiscardAll(false); setDiscardAllError('') }} onConfirm={() => void discardAll()} />
    </div>
  )
}
