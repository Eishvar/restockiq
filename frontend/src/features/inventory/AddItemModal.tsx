import { useState } from 'react'
import { Button, Modal, useToast } from '../../components/ui'
import { useMe } from '../auth/api'
import { useAddItem, useStorageAreas, useSuppliers } from './api'
import ManageListsModal from './ManageListsModal'
import QtyInput, { inputCls } from './QtyInput'
import { plainUnits, toBase } from './units'

const BASE_LABEL = { g: 'weight (g / kg)', ml: 'liquid (ml / L)', pcs: 'pieces' } as const

function Field({ label, hint, action, children }: { label: string; hint?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="block text-sm">
      <div className="mb-1 flex items-center justify-between gap-2">
        <label className="font-medium">
          {label}
        </label>
        {action}
      </div>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </div>
  )
}

type Props = { open: boolean; today: string; onClose: () => void }

/** Add a new raw item to stock. Quantities are converted to base units before they are sent. */
export default function AddItemModal({ open, today, onClose }: Props) {
  const suppliers = useSuppliers()
  const areas = useStorageAreas()
  const add = useAddItem()
  const toast = useToast()
  const me = useMe()

  const [name, setName] = useState('')
  const [storage, setStorage] = useState('dry')
  const [baseUom, setBaseUom] = useState<'g' | 'ml' | 'pcs'>('g')
  const [supplierId, setSupplierId] = useState('')
  const [packName, setPackName] = useState('')
  const [packSize, setPackSize] = useState('')
  const [packUnitIdx, setPackUnitIdx] = useState(0)
  const [price, setPrice] = useState('')
  const [shelfLife, setShelfLife] = useState('')
  const [qty, setQty] = useState(0)
  const [bought, setBought] = useState(today)
  const [managing, setManaging] = useState(false)

  // A supplier or place removed while this form is open must not stay selected.
  const supplierValue = suppliers.data?.some((s) => String(s.id) === supplierId) ? supplierId : ''
  const storageValue = areas.data?.some((a) => a.key === storage) ? storage : (areas.data?.[0]?.key ?? storage)

  const packUnits = plainUnits(baseUom)
  const packSizeBase = toBase(parseFloat(packSize) || 0, packUnits[Math.min(packUnitIdx, packUnits.length - 1)])
  const valid = name.trim() && packName.trim() && packSizeBase > 0 && price !== '' && parseInt(shelfLife) >= 1

  function reset() {
    setName('')
    setPackName('')
    setPackSize('')
    setPrice('')
    setShelfLife('')
    setQty(0)
    setSupplierId('')
    setBought(today)
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    try {
      await add.mutateAsync({
        name: name.trim(),
        storage: storageValue,
        base_uom: baseUom,
        supplier_id: supplierValue ? Number(supplierValue) : null,
        pack_uom: packName.trim(),
        pack_size_base: packSizeBase,
        pack_price_rm: parseFloat(price),
        shelf_life_days: parseInt(shelfLife),
        qty_base: qty,
        last_purchased_on: qty > 0 ? bought || today : null,
      })
      toast(`${name.trim()} added to your stock`, 'success')
      reset()
      onClose()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not add the item', 'error')
    }
  }

  const manageLink = (
    <button type="button" onClick={() => setManaging(true)} className="text-xs font-semibold text-emerald-800 underline underline-offset-2">
      {me.data?.role === 'owner' ? 'Add / rename / remove' : 'Add / rename'}
    </button>
  )

  return (
    <>
      <Modal open={open} title="Add an item, supplier or place" onClose={onClose}>
        <form onSubmit={submit} className="space-y-3">
          <Field label="Item name">
            <input required value={name} onChange={(e) => setName(e.target.value)} className={`${inputCls} w-full`} placeholder="e.g. Sweet soy sauce 2L" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Where is it kept?" action={manageLink}>
              <select aria-label="Where is it kept?" value={storageValue} onChange={(e) => setStorage(e.target.value)} className={`${inputCls} w-full`}>
                {(areas.data ?? [{ key: 'dry', name: 'Dry store', items: 0 }]).map((a) => (
                  <option key={a.key} value={a.key}>
                    {a.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Measured as">
              <select
                aria-label="Measured as"
                value={baseUom}
                onChange={(e) => {
                  setBaseUom(e.target.value as 'g' | 'ml' | 'pcs')
                  setPackUnitIdx(0)
                }}
                className={`${inputCls} w-full`}
              >
                {Object.entries(BASE_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <Field label="Supplier" action={manageLink}>
            <select aria-label="Supplier" value={supplierValue} onChange={(e) => setSupplierId(e.target.value)} className={`${inputCls} w-full`}>
              <option value="">No supplier yet</option>
              {suppliers.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="How it is sold" hint='e.g. "BAG (10kg)"'>
              <input aria-label="How it is sold" required value={packName} onChange={(e) => setPackName(e.target.value)} className={`${inputCls} w-full`} />
            </Field>
            <Field label="Amount in one pack">
              <span className="flex gap-1">
                <input
                  aria-label="Amount in one pack"
                  required
                  type="number"
                  min={0}
                  step="any"
                  value={packSize}
                  onChange={(e) => setPackSize(e.target.value)}
                  className={`${inputCls} w-full`}
                />
                <select aria-label="Pack unit" value={packUnitIdx} onChange={(e) => setPackUnitIdx(Number(e.target.value))} className={inputCls}>
                  {packUnits.map((u, i) => (
                    <option key={u.key} value={i}>
                      {u.label}
                    </option>
                  ))}
                </select>
              </span>
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Price per pack (RM)">
              <input aria-label="Price per pack" required type="number" min={0} step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} className={`${inputCls} w-full`} />
            </Field>
            <Field label="Shelf life (days)" hint="How many days it stays good after you buy it">
              <input aria-label="Shelf life in days" required type="number" min={1} value={shelfLife} onChange={(e) => setShelfLife(e.target.value)} className={`${inputCls} w-full`} />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="How much do you have now?">
              <QtyInput key={baseUom + packSizeBase} baseQty={qty} onChange={setQty} item={{ base_uom: baseUom, pack_size_base: packSizeBase }} />
            </Field>
            <Field label="Date you bought it" hint={qty > 0 ? undefined : 'Used when you have some in stock'}>
              <input aria-label="Date you bought it" type="date" max={today} value={bought} onChange={(e) => setBought(e.target.value)} className={`${inputCls} w-full`} />
            </Field>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!valid || add.isPending}>
              {add.isPending ? 'Adding…' : 'Add item'}
            </Button>
          </div>
        </form>
      </Modal>
      <ManageListsModal
        open={open && managing}
        onClose={() => setManaging(false)}
        onCreated={(kind, id) => (kind === 'supplier' ? setSupplierId(id) : setStorage(id))}
      />
    </>
  )
}
