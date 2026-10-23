import { useState } from 'react'
import { Badge, Button, Card, Table, useToast } from '../../components/ui'
import { useConfirmOnboarding, usePatchItem, type InventoryList, type ItemPatch } from './api'
import QuickNoteModal from '../assistant/QuickNoteModal'
import AddItemModal from './AddItemModal'
import QtyInput, { inputCls } from './QtyInput'
import { StatusBadge, STORAGE_LABEL, STORAGE_ORDER, fmtDate } from './shared'

/** One-time setup for the owner: check the opening stock, fix anything wrong, then confirm. */
export default function OnboardingWizard({ data }: { data: InventoryList }) {
  const [edits, setEdits] = useState<Record<number, ItemPatch>>({})
  const [adding, setAdding] = useState(false)
  const [noting, setNoting] = useState(false)
  const [busy, setBusy] = useState(false)
  const patch = usePatchItem()
  const confirm = useConfirmOnboarding()
  const toast = useToast()

  const edit = (id: number, change: ItemPatch) => setEdits((e) => ({ ...e, [id]: { ...e[id], ...change } }))
  const changed = Object.keys(edits).length

  async function finish() {
    setBusy(true)
    try {
      await Promise.all(Object.entries(edits).map(([id, p]) => patch.mutateAsync({ id: Number(id), patch: p })))
      await confirm.mutateAsync()
      toast('Your stock is saved. You can now plan purchases.', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not save your stock', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Tell RestockAI what you have in stock (one time)</h1>
        <p className="mt-1 text-sm text-slate-600">
          We have filled in an example. Check each line: how much you have, when you last bought it and how many days it
          stays good. Change anything that is wrong, then confirm. You can edit this later on the Inventory page.
        </p>
      </div>

      {STORAGE_ORDER.map((storage) => {
        const rows = data.items.filter((i) => i.storage === storage)
        if (!rows.length) return null
        return (
          <Card key={storage} title={`${STORAGE_LABEL[storage]} (${rows.length})`}>
            <Table head={['Item', 'How much you have', 'Last bought', 'Good for (days)', '']}>
              {rows.map((r) => {
                const e = edits[r.ingredient_id] ?? {}
                const bought = e.last_purchased_on !== undefined ? e.last_purchased_on : r.last_purchased_on
                return (
                  <tr key={r.ingredient_id}>
                    <td className="font-medium">{r.name}</td>
                    <td>
                      <QtyInput baseQty={e.qty_base ?? r.qty_base} item={r} onChange={(q) => edit(r.ingredient_id, { qty_base: q })} />
                    </td>
                    <td>
                      <input
                        type="date"
                        aria-label="Last bought"
                        max={data.today}
                        value={bought ?? ''}
                        onChange={(ev) => edit(r.ingredient_id, { last_purchased_on: ev.target.value || null })}
                        className={inputCls}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min={1}
                        aria-label="Shelf life in days"
                        value={e.shelf_life_days ?? r.shelf_life_days}
                        onChange={(ev) => ev.target.value && edit(r.ingredient_id, { shelf_life_days: parseInt(ev.target.value) })}
                        className={`${inputCls} w-20`}
                      />
                    </td>
                    <td>{r.status !== 'ok' && <StatusBadge row={r} />}</td>
                  </tr>
                )
              })}
            </Table>
          </Card>
        )
      })}

      <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:-mx-6 md:px-6">
        <div className="flex items-center gap-3 text-sm text-slate-600">
          <Button variant="secondary" onClick={() => setNoting(true)}>
            ⚡ Quick add from a note
          </Button>
          <Button variant="secondary" onClick={() => setAdding(true)}>
            + Add item
          </Button>
          {changed > 0 && <Badge tone="warn">{changed} changed</Badge>}
          <span className="hidden sm:inline">Stock as of {fmtDate(data.today)}</span>
        </div>
        <Button onClick={finish} disabled={busy}>
          {busy ? 'Saving…' : 'Confirm my stock'}
        </Button>
      </div>

      <AddItemModal open={adding} today={data.today} onClose={() => setAdding(false)} />
      <QuickNoteModal open={noting} data={data} onClose={() => setNoting(false)} />
    </div>
  )
}
