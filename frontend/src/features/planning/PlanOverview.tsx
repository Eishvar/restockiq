import { Badge, Card, EmptyState, Stat } from '../../components/ui'
import type { Dashboard } from '../dashboard/api'
import { rm } from './format'

/** Stock health and biggest spend for the latest plan, shown side by side. */
export default function PlanOverview({ d }: { d: Dashboard }) {
  const maxSpend = Math.max(...d.top_spend.map((s) => s.total_rm), 0)
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card title="Stock health">
        <div className="grid grid-cols-3 gap-3 text-center">
          <Stat label="Fine" value={d.inventory.ok} />
          <Stat label="Use soon" value={d.inventory.expiring_soon} />
          <Stat label="Expired" value={d.inventory.expired} />
        </div>
        {d.inventory.expiring_soon > 0 && (
          <ul className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {d.inventory.expiring_items.map((item) => (
              <li key={item.name} className="flex items-center justify-between gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
                <span className="min-w-0 break-words">{item.name}</span>
                <Badge tone="warn">{item.days_left}d</Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Where the money goes">
        {d.top_spend.length === 0 ? (
          <EmptyState title="Nothing to show yet" />
        ) : (
          <ul className="space-y-2">
            {d.top_spend.map((s) => (
              <li key={s.name} className="text-sm">
                <div className="flex justify-between"><span>{s.name}</span><span className="font-medium">{rm(s.total_rm)}</span></div>
                <div className="mt-1 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-brand-royal" style={{ width: `${maxSpend > 0 ? Math.max(0, Math.min(100, s.total_rm / maxSpend * 100)) : 0}%` }} /></div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
