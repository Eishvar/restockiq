import { Badge } from '../../components/ui'
import type { StorageArea, Status } from './api'

const STANDARD_NAME: Record<string, string> = { freezer: 'Freezer', chiller: 'Chiller', dry: 'Dry store' }

/** The name people see for a storage place. Falls back to the standard names while the list is loading. */
export const areaName = (areas: StorageArea[] | undefined, key: string) =>
  areas?.find((a) => a.key === key)?.name ?? STANDARD_NAME[key] ?? key

export const fmtDate = (iso: string | null) =>
  iso ? new Date(iso + 'T00:00').toLocaleDateString('en-MY', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

export function StatusBadge({ row }: { row: { status: Status; days_left: number | null } }) {
  const tone: Record<Status, 'good' | 'warn' | 'bad'> = { ok: 'good', expiring_soon: 'warn', expired: 'bad' }
  const text =
    row.status === 'expired'
      ? 'Expired'
      : row.status === 'expiring_soon'
        ? `Expires in ${row.days_left} day${row.days_left === 1 ? '' : 's'}`
        : 'OK'
  return <Badge tone={tone[row.status]}>{text}</Badge>
}
