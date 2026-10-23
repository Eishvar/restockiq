import { Badge } from '../../components/ui'
import type { Status } from './api'

export const STORAGE_LABEL = { freezer: 'Freezer', chiller: 'Chiller', dry: 'Dry store' } as const
export const STORAGE_ORDER = ['freezer', 'chiller', 'dry'] as const

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
