import { useState } from 'react'
import { Button, Card, EmptyState, SegmentedControl, Table, Tooltip, useToast } from '../../components/ui'
import { useMe } from '../auth/api'
import {
  useDiscardExpired,
  useInventory,
  usePatchItem,
  useRemoveItem,
  type InventoryRow,
  type ItemPatch,
  type Status,
} from './api'
import QuickNoteModal from '../assistant/QuickNoteModal'
import AddItemModal from './AddItemModal'
import HistoryModal from './HistoryModal'
import OnboardingWizard from './OnboardingWizard'
import QtyInput, { inputCls } from './QtyInput'
import { StatusBadge, STORAGE_LABEL, fmtDate } from './shared'

type Filter = 'all' | Status

function ItemRow({
  row, today, canEditAll, onHistory,
}: { row: InventoryRow; today: string; canEditAll: boolean; onHistory: () => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<ItemPatch>({})
  const patch = usePatchItem()
  const remove = useRemoveItem()
  const discard = useDiscardExpired()
  const toast = useToast()
  const fail = (err: unknown) => toast(err instanceof Error ? err.message : 'Something went wrong', 'error')

  async function save() {
    try {
      if (Object.keys(draft).length) await patch.mutateAsync({ id: row.ingredient_id, patch: draft })
      toast(`${row.name} updated`, 'success')
      setEditing(false)
      setDraft({})
    } catch (err) {
      fail(err)
    }
  }

  async function onRemove() {
    if (!window.confirm(`Remove ${row.name} from your stock? Its history is kept.`)) return
    try {
      await remove.mutateAsync(row.ingredient_id)
      toast(`${row.name} removed`, 'success')
    } catch (err) {
      fail(err)
    }
  }

  async function onDiscard() {
    try {
      await discard.mutateAsync(row.ingredient_id)
      toast(`${row.name} thrown away`, 'success')
    } catch (err) {
      fail(err)
    }
  }

  const manager = (label: string, button: React.ReactNode) =>
    canEditAll ? button : <Tooltip text={`Only managers and owners can ${label}`}>{button}</Tooltip>

  return (
    <tr className={row.status === 'expired' ? 'bg-red-50' : ''}>
      <td>
        <div className="font-medium">{row.name}</div>
        <div className="text-xs text-slate-500">
          {STORAGE_LABEL[row.storage]}
          {row.supplier_name ? ` · ${row.supplier_name}` : ''}
        </div>
      </td>
      <td className="whitespace-nowrap">
        {editing ? (
          <QtyInput baseQty={draft.qty_base ?? row.qty_base} item={row} onChange={(q) => setDraft((d) => ({ ...d, qty_base: q }))} />
        ) : (
          row.display_qty
        )}
      </td>
      <td className="whitespace-nowrap">
        {editing && canEditAll ? (
          <input
            type="date"
            aria-label="Last bought"
            max={today}
            value={draft.last_purchased_on !== undefined ? (draft.last_purchased_on ?? '') : (row.last_purchased_on ?? '')}
            onChange={(e) => setDraft((d) => ({ ...d, last_purchased_on: e.target.value || null }))}
            className={inputCls}
          />
        ) : (
          fmtDate(row.last_purchased_on)
        )}
      </td>
      <td className="whitespace-nowrap">
        {editing && canEditAll ? (
          <input
            type="number"
            min={1}
            aria-label="Shelf life in days"
            value={draft.shelf_life_days ?? row.shelf_life_days}
            onChange={(e) => e.target.value && setDraft((d) => ({ ...d, shelf_life_days: parseInt(e.target.value) }))}
            className={`${inputCls} w-20`}
          />
        ) : (
          `${row.shelf_life_days} days`
        )}
      </td>
      <td className="whitespace-nowrap">{fmtDate(row.expires_on)}</td>
      <td>
        <StatusBadge row={row} />
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
              {row.status === 'expired' && (
                <Button variant="danger" onClick={onDiscard} disabled={discard.isPending}>
                  Discard
                </Button>
              )}
              <Button variant="ghost" onClick={() => setEditing(true)}>
                Edit
              </Button>
              <Button variant="ghost" onClick={onHistory}>
                History
              </Button>
              {manager('remove items', <Button variant="ghost" onClick={onRemove} disabled={!canEditAll}>Remove</Button>)}
            </>
          )}
        </div>
      </td>
    </tr>
  )
}

export default function InventoryPage() {
  const { data, isLoading, error } = useInventory()
  const me = useMe()
  const discard = useDiscardExpired()
  const toast = useToast()
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [storage, setStorage] = useState('')
  const [adding, setAdding] = useState(false)
  const [noting, setNoting] = useState(false)
  const [history, setHistory] = useState<InventoryRow | null>(null)

  if (isLoading) return <p className="text-sm text-slate-500">Loading your stock…</p>
  if (error || !data) return <EmptyState title="Could not load your stock" hint={error?.message ?? 'Please try again.'} />

  const role = me.data?.role
  const canEditAll = role === 'owner' || role === 'manager'

  // The owner sets up stock once; everyone else sees the normal page with a short note.
  if (!data.onboarded && role === 'owner') return <OnboardingWizard data={data} />

  const expired = data.items.filter((i) => i.status === 'expired')
  const soon = data.items.filter((i) => i.status === 'expiring_soon')
  const rows = data.items.filter(
    (i) =>
      (filter === 'all' || i.status === filter) &&
      (!storage || i.storage === storage) &&
      i.name.toLowerCase().includes(query.trim().toLowerCase()),
  )

  async function discardAll() {
    try {
      const r = await discard.mutateAsync(null)
      toast(`${r.discarded.length} expired item(s) thrown away`, 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not discard', 'error')
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
          <p className="text-sm text-slate-600">What you have now, as of {fmtDate(data.today)}.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setNoting(true)}>⚡ Quick add from a note</Button>
          {canEditAll ? addButton : <Tooltip text="Only managers and owners can add items">{addButton}</Tooltip>}
        </div>
      </div>

      {!data.onboarded && (
        <div className="rounded-xl border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900">
          The owner has not confirmed the opening stock yet. These numbers are an example until they do.
        </div>
      )}

      {expired.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900">
          <span>
            <strong>{expired.length} item{expired.length === 1 ? ' has' : 's have'} expired:</strong>{' '}
            {expired.map((i) => i.name).join(', ')}. Throw them away so they are not counted as stock?
          </span>
          <Button variant="danger" onClick={discardAll} disabled={discard.isPending}>
            Discard expired
          </Button>
        </div>
      )}
      {soon.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <strong>Use soon:</strong> {soon.map((i) => `${i.name} (${i.days_left} day${i.days_left === 1 ? '' : 's'})`).join(', ')}.
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
          <Table head={['Item', 'In stock', 'Last bought', 'Good for', 'Expires', 'Status', '']}>
            {rows.map((r) => (
              <ItemRow key={r.ingredient_id} row={r} today={data.today} canEditAll={canEditAll} onHistory={() => setHistory(r)} />
            ))}
          </Table>
        )}
      </Card>

      <AddItemModal open={adding} today={data.today} onClose={() => setAdding(false)} />
      <QuickNoteModal open={noting} data={data} onClose={() => setNoting(false)} />
      <HistoryModal ingredientId={history?.ingredient_id ?? null} name={history?.name ?? ''} onClose={() => setHistory(null)} />
    </div>
  )
}
