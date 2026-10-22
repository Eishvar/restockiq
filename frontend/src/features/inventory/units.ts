// Quantities are stored in base units (g / ml / pcs). The owner can type them in friendlier units.
export type Unit = { key: string; label: string; factor: number }

type PackInfo = { base_uom: string; pack_size_base: number }

/** Plain units for a base unit, without the pack option. */
export function plainUnits(baseUom: string): Unit[] {
  if (baseUom === 'g')
    return [
      { key: 'kg', label: 'kg', factor: 1000 },
      { key: 'g', label: 'g', factor: 1 },
    ]
  if (baseUom === 'ml')
    return [
      { key: 'L', label: 'L', factor: 1000 },
      { key: 'ml', label: 'ml', factor: 1 },
    ]
  return [{ key: 'pcs', label: 'pcs', factor: 1 }]
}

/** Plain units plus "packs" when the pack size is known. */
export function unitsFor(item: PackInfo): Unit[] {
  const units = plainUnits(item.base_uom)
  return item.pack_size_base > 0 ? [...units, { key: 'pack', label: 'packs', factor: item.pack_size_base }] : units
}

export const toBase = (value: number, unit: Unit) => value * unit.factor
export const fromBase = (base: number, unit: Unit) => base / unit.factor

/** Up to 3 decimals, no trailing zeros ("2.4", "1500"). */
export const fmtNum = (n: number) => String(Math.round(n * 1000) / 1000)
