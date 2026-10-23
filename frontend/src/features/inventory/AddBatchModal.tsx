import { useState } from 'react'
import { Button, Modal, useToast } from '../../components/ui'
import { useAddBatch, type InventoryRow } from './api'
import QtyInput, { inputCls } from './QtyInput'

type Props = { item: InventoryRow | null; today: string; onClose: () => void }

/** Record stock bought on one day. It becomes its own batch, so its shelf life runs from that day. */
export default function AddBatchModal({ item, today, onClose }: Props) {
  // Keyed by item so the form starts fresh (with that item's defaults) each time it opens.
  return item ? <BatchForm key={item.ingredient_id} item={item} today={today} onClose={onClose} /> : null
}

function BatchForm({ item, today, onClose }: { item: InventoryRow; today: string; onClose: () => void }) {
  const add = useAddBatch()
  const toast = useToast()
  const [qty, setQty] = useState(0)
  const [bought, setBought] = useState(today)
  const [shelf, setShelf] = useState(String(item.shelf_life_days))
  const [price, setPrice] = useState(String(item.pack_price_rm))

  const valid = qty > 0 && bought !== '' && parseInt(shelf) >= 1 && price !== ''

  async function save() {
    try {
      await add.mutateAsync({
        ingredientId: item.ingredient_id,
        batch: { qty_base: qty, procured_on: bought, shelf_life_days: parseInt(shelf), pack_price_rm: parseFloat(price) },
      })
      toast(`Batch of ${item.name} added`, 'success')
      onClose()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not add the batch', 'error')
    }
  }

  return (
    <Modal open title={`Add stock: ${item.name}`} onClose={onClose}>
      <div className="space-y-3 text-sm">
        <p className="text-slate-600">
          Stock bought on a different day is kept as its own batch, so each one expires on its own date. If you already have a
          batch from the same day, this is added to it.
        </p>
        <label className="block">
          <span className="mb-1 block font-medium">How much did you buy?</span>
          <QtyInput baseQty={qty} onChange={setQty} item={item} />
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">Bought on</span>
          <input type="date" max={today} value={bought} onChange={(e) => setBought(e.target.value)} className={inputCls} />
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">Good for (days)</span>
          <input type="number" min={1} value={shelf} onChange={(e) => setShelf(e.target.value)} className={`${inputCls} w-24`} />
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">Price per pack ({item.pack_uom}), RM</span>
          <input type="number" min={0} step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} className={`${inputCls} w-28`} />
        </label>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} disabled={!valid || add.isPending}>
            Add batch
          </Button>
        </div>
      </div>
    </Modal>
  )
}
