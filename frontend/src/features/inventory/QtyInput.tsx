import { useEffect, useState } from 'react'
import { fmtNum, fromBase, toBase, unitsFor, type Unit } from './units'

export const inputCls =
  'rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm disabled:bg-slate-100 disabled:text-slate-500'

type Props = {
  baseQty: number
  onChange: (baseQty: number) => void
  item: { base_uom: string; pack_size_base: number }
  disabled?: boolean
}

/** Quantity box with a unit picker (kg / L / pcs, or whole packs). Always reports base units. */
export default function QtyInput({ baseQty, onChange, item, disabled }: Props) {
  const units = unitsFor(item)
  const [unitKey, setUnitKey] = useState(units[0].key)
  const unit: Unit = units.find((u) => u.key === unitKey) ?? units[0]
  const [text, setText] = useState(fmtNum(fromBase(baseQty, unit)))

  // Keep the box in step when the quantity is changed from outside (e.g. after saving).
  useEffect(() => {
    if (Math.abs(toBase(parseFloat(text) || 0, unit) - baseQty) > 0.001) setText(fmtNum(fromBase(baseQty, unit)))
  }, [baseQty, unit, text])

  return (
    <span className="inline-flex items-center gap-1">
      <input
        type="number"
        min={0}
        step="any"
        inputMode="decimal"
        aria-label="Quantity"
        disabled={disabled}
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          const n = parseFloat(e.target.value)
          if (!Number.isNaN(n) && n >= 0) onChange(toBase(n, unit))
        }}
        className={`${inputCls} w-24`}
      />
      <select
        aria-label="Unit"
        disabled={disabled}
        value={unit.key}
        onChange={(e) => {
          const next = units.find((u) => u.key === e.target.value) ?? units[0]
          setUnitKey(next.key)
          setText(fmtNum(fromBase(baseQty, next)))
        }}
        className={inputCls}
      >
        {units.map((u) => (
          <option key={u.key} value={u.key}>
            {u.label}
          </option>
        ))}
      </select>
    </span>
  )
}
