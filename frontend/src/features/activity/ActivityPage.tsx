import { ApiError } from '../../api/client'
import { Badge, Card, EmptyState, Table } from '../../components/ui'
import { useActivity, type ActivityRow } from './api'

const roleTone = { owner: 'good', manager: 'warn', staff: 'neutral' } as const

const humanise = (action: string) => {
  const text = action.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

const when = (iso: string) =>
  new Date(iso).toLocaleString('en-MY', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

function Details({ row }: { row: ActivityRow }) {
  const parts: string[] = []
  if (row.entity_type) parts.push(`${row.entity_type.replace(/_/g, ' ')}${row.entity_id ? ` #${row.entity_id}` : ''}`)
  if (row.details) parts.push(Object.entries(row.details).map(([k, v]) => `${k.replace(/_/g, ' ')}: ${JSON.stringify(v)}`).join(', '))
  return <span className="text-slate-600">{parts.join(' · ') || '—'}</span>
}

export default function ActivityPage() {
  const { data, isLoading, error } = useActivity()

  let body
  if (isLoading) body = <p className="text-sm text-slate-500">Loading…</p>
  else if (error instanceof ApiError && error.status === 403)
    body = (
      <EmptyState
        title="Only managers and owners can see the activity record"
        hint="Switch user (top right) to Siti or Ah Hock to view it."
      />
    )
  else if (error) body = <EmptyState title="Could not load the activity record" hint={error.message} />
  else if (!data?.length)
    body = (
      <EmptyState
        title="Nothing recorded yet"
        hint="Every plan, approval and stock change is written here with who did it and when."
      />
    )
  else
    body = (
      <Table head={['When', 'Who', 'What', 'Details']}>
        {data.map((r) => (
          <tr key={r.id}>
            <td className="whitespace-nowrap">{when(r.ts)}</td>
            <td className="whitespace-nowrap">
              {r.user_name ?? 'System'}{' '}
              {r.role && <Badge tone={roleTone[r.role as keyof typeof roleTone] ?? 'neutral'}>{r.role}</Badge>}
            </td>
            <td className="font-medium">{humanise(r.action)}</td>
            <td>
              <Details row={r} />
            </td>
          </tr>
        ))}
      </Table>
    )

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <h1 className="text-xl font-semibold">Activity</h1>
      <p className="text-sm text-slate-600">A simple record of who did what, so everything can be traced.</p>
      <Card>{body}</Card>
    </div>
  )
}
