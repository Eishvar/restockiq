import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Button, Card } from '../../components/ui'
import { useMe } from '../auth/api'
import { fmtDay } from '../planning/format'
import { useSetupStatus } from '../setup/api'
import ImportSalesModal from './ImportSalesModal'
import { usePosStatus } from './api'

/** Dashboard card: is the POS connected, how fresh are the sales, and the Import button. */
export default function PosCard() {
  const me = useMe()
  const pos = usePosStatus()
  const setup = useSetupStatus(me.data?.role === 'owner')
  const [importing, setImporting] = useState(false)
  const canImport = me.data?.role === 'owner' || me.data?.role === 'manager'
  const p = pos.data

  return (
    <Card title="Sales from your POS">
      {pos.isLoading || !p ? (
        <p className="text-sm text-slate-500">{pos.error ? pos.error.message : 'Loading…'}</p>
      ) : !p.provider ? (
        <>
          <p className="text-sm text-slate-600">No POS connected yet. Connect FeedMe so RestockAI can learn from your daily sales.</p>
          {me.data?.role === 'owner' ? (
            <Link to="/setup" className="mt-2 inline-block text-sm font-medium text-brand-royal underline">Finish setup</Link>
          ) : (
            <p className="mt-2 text-xs text-slate-500">Ask the owner to connect it.</p>
          )}
        </>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium">FeedMe</span>
            <Badge tone="good">Connected</Badge>
            <Badge tone="warn">simulated</Badge>
            {setup.data?.currency && <Badge>{setup.data.currency}</Badge>}
          </div>
          <dl className="mt-3 space-y-1 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Sales up to</dt>
              <dd className="font-medium">{p.latest_sales_date ? fmtDay(p.latest_sales_date) : 'none yet'}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Next day to import</dt>
              <dd className="font-medium">{p.next_to_import ? fmtDay(p.next_to_import) : 'Up to date'}</dd>
            </div>
            {p.last_import && (
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">Last import</dt>
                <dd className="text-right">
                  {p.last_import.days} day{p.last_import.days === 1 ? '' : 's'}
                  {p.last_import.user_name && <> by {p.last_import.user_name}</>}
                </dd>
              </div>
            )}
          </dl>
          <p className="mt-3 text-xs text-slate-500">
            Export your sales from FeedMe as a CSV file, then upload it here. Automatic syncing comes later.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {canImport ? (
              <Button onClick={() => setImporting(true)}>Import sales</Button>
            ) : (
              <span className="text-xs text-slate-500">Managers and the owner can import sales.</span>
            )}
            <Link to="/pos/feedme" target="_blank" rel="noreferrer" className="inline-flex items-center rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50">
              Open FeedMe (simulated)
            </Link>
          </div>
          <ImportSalesModal open={importing} onClose={() => setImporting(false)} />
        </>
      )}
    </Card>
  )
}
