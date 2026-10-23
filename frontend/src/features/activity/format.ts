const LABELS: Record<string, string> = {
  horizon_days: 'days ahead',
  risk_profile: 'stock setting',
  final_packs: 'packs',
  suggested_packs: 'suggested packs',
  ingredient_name: 'item',
  supplier_name: 'supplier',
  qty_base: 'stock quantity',
  name: 'name',
}

function readable(value: unknown, key = ''): string {
  if (value === null || value === undefined || value === '') return 'Not set'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number') return value.toLocaleString('en-MY')
  if (Array.isArray(value)) return value.length ? value.map((item) => readable(item, key)).join(', ') : 'None'
  if (typeof value === 'object') {
    return Object.entries(value).map(([name, item]) =>
      `${LABELS[name] ?? name.replace(/_/g, ' ')}: ${readable(item, name)}`,
    ).join('; ') || 'None'
  }
  const text = String(value)
  return ['role', 'status', 'risk_profile', 'action', 'channel'].includes(key)
    ? text.replace(/_/g, ' ')
    : text
}

export function formatActivityDetails(details: Record<string, unknown> | null, entity?: string | null, entityId?: string | null) {
  const phrases: string[] = []
  if (entity) phrases.push(`${entity.replace(/_/g, ' ')}${entityId ? ` #${entityId}` : ''}`)
  for (const [key, value] of Object.entries(details ?? {})) {
    const label = LABELS[key] ?? key.replace(/_/g, ' ')
    if (value === null || value === undefined || value === '') continue
    if (key === 'horizon_days') phrases.push(`${readable(value)} ${value === 1 ? 'day ahead' : label}`)
    else phrases.push(`${label}: ${readable(value, key)}`)
  }
  return phrases
}
