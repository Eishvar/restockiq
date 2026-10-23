import { useState } from 'react'
import { ApiError } from '../../api/client'
import { Button, Modal, Tooltip, useToast } from '../../components/ui'
import { UNAVAILABLE_TEXT, useAiStatus, useSuggestShelfLife } from '../assistant/api'
import { useAddItem, useSuppliers } from './api'
import QtyInput, { inputCls } from './QtyInput'
import { plainUnits, toBase } from './units'

const BASE_LABEL = { g: 'weight (g / kg)', ml: 'liquid (ml / L)', pcs: 'pieces' } as const

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  )
}

type Props = { open: boolean; today: string; onClose: () => void }

/** Add a new raw item to stock. Quantities are converted to base units before they are sent. */
export default function AddItemModal({ open, today, onClose }: Props) {
  const suppliers = useSuppliers()
  const add = useAddItem()
  const toast = useToast()

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

  const packUnits = plainUnits(baseUom)
  const packSizeBase = toBase(parseFloat(packSize) || 0, packUnits[Math.min(packUnitIdx, packUnits.length - 1)])
  const valid = name.trim() && packName.trim() && packSizeBase > 0 && price !== '' && parseInt(shelfLife) >= 1

  // "Suggest": the AI proposes shelf life, storage and unit; the person can change all of it before adding.
  const status = useAiStatus()
  const suggesting = useSuggestShelfLife()
  const [suggestionId, setSuggestionId] = useState<number | null>(null)
  const [suggestMsg, setSuggestMsg] = useState('')
  const [suggestFailed, setSuggestFailed] = useState(false)
  const aiOff = status.data?.available === false || suggestFailed

  async function suggest() {
    setSuggestFailed(false)
    try {
      const s = await suggesting.mutateAsync({ name: name.trim() })
      setShelfLife(String(s.shelf_life_days))
      setStorage(s.storage)
      setBaseUom(s.base_uom)
      setPackUnitIdx(0)
      setSuggestionId(s.suggestion_id)
      setSuggestMsg(`Suggested: ${s.shelf_life_days} days. ${s.rationale} Change it if you know better.`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setSuggestFailed(true)
        setSuggestMsg(`${UNAVAILABLE_TEXT}.`)
      } else toast(err instanceof Error ? err.message : 'Could not get a suggestion', 'error')
    }
  }

  function reset() {
    setSuggestionId(null)
    setSuggestMsg('')
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
        storage,
        base_uom: baseUom,
        supplier_id: supplierId ? Number(supplierId) : null,
        pack_uom: packName.trim(),
        pack_size_base: packSizeBase,
        pack_price_rm: parseFloat(price),
        shelf_life_days: parseInt(shelfLife),
        qty_base: qty,
        last_purchased_on: qty > 0 ? bought || today : null,
        suggestion_id: suggestionId,
      })
      toast(`${name.trim()} added to your stock`, 'success')
      reset()
      onClose()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not add the item', 'error')
    }
  }

  return (
    <Modal open={open} title="Add an item" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <Field label="Item name">
          <input required value={name} onChange={(e) => setName(e.target.value)} className={`${inputCls} w-full`} placeholder="e.g. Sweet soy sauce 2L" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Where is it kept?">
            <select value={storage} onChange={(e) => setStorage(e.target.value)} className={`${inputCls} w-full`}>
              <option value="dry">Dry store</option>
              <option value="chiller">Chiller</option>
              <option value="freezer">Freezer</option>
            </select>
          </Field>
          <Field label="Measured as">
            <select
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
        <Field label="Supplier">
          <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)} className={`${inputCls} w-full`}>
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
            <input required value={packName} onChange={(e) => setPackName(e.target.value)} className={`${inputCls} w-full`} />
          </Field>
          <Field label="Amount in one pack">
            <span className="flex gap-1">
              <input
                required
                type="number"
                min={0}
                step="any"
                value={packSize}
                onChange={(e) => setPackSize(e.target.value)}
                className={`${inputCls} w-full`}
              />
              <select value={packUnitIdx} onChange={(e) => setPackUnitIdx(Number(e.target.value))} className={inputCls}>
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
            <input required type="number" min={0} step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} className={`${inputCls} w-full`} />
          </Field>
          <Field label="Shelf life (days)" hint={suggestMsg || 'How long it stays good after you buy it'}>
            <span className="flex gap-1">
              <input required type="number" min={1} value={shelfLife} onChange={(e) => setShelfLife(e.target.value)} className={`${inputCls} w-full`} />
              {aiOff ? (
                <Tooltip text={UNAVAILABLE_TEXT}>
                  <Button type="button" variant="secondary" disabled>Suggest</Button>
                </Tooltip>
              ) : (
                <Button type="button" variant="secondary" onClick={suggest} disabled={!name.trim() || suggesting.isPending}>
                  {suggesting.isPending ? 'Suggesting…' : 'Suggest'}
                </Button>
              )}
            </span>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="How much do you have now?">
            <QtyInput key={baseUom + packSizeBase} baseQty={qty} onChange={setQty} item={{ base_uom: baseUom, pack_size_base: packSizeBase }} />
          </Field>
          <Field label="Last bought on">
            <input type="date" max={today} value={bought} onChange={(e) => setBought(e.target.value)} className={`${inputCls} w-full`} disabled={qty <= 0} />
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
  )
}
