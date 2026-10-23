import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Button, EmptyState, useToast } from '../../components/ui'
import { useMe } from '../auth/api'
import { inputCls } from '../inventory/QtyInput'
import { fmtDay, num, rm } from '../planning/format'
import { downloadFeedMeCsv, useFeedMeDays, useFeedMePreview } from './api'

/**
 * A stand-in for the FeedMe till, so the "export sales -> upload to RestockIQ" step can be shown in a demo.
 * It is deliberately plain (no FeedMe logo or branding) and says so on screen. The data is synthetic.
 */
export default function FeedMePage() {
  const me = useMe()
  const days = useFeedMeDays()
  const toast = useToast()
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [busy, setBusy] = useState(false)

  const list = days.data ?? []
  const newest = list[0]?.date ?? ''
  // Until the person picks dates: from the oldest day not yet in RestockIQ (else just the newest day) to the newest day.
  const notSent = list.filter((d) => !d.imported).map((d) => d.date).sort()
  const start = from || notSent[0] || newest
  const end = to || newest
  const preview = useFeedMePreview(start, end)

  const allowed = me.data?.role === 'owner' || me.data?.role === 'manager'

  async function download() {
    setBusy(true)
    try {
      const name = await downloadFeedMeCsv(start, end)
      toast(`Downloaded ${name}. Now upload it in RestockIQ (Dashboard → Import sales).`, 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not export', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-stone-100">
      <div className="bg-amber-400 px-4 py-2 text-center text-sm font-medium text-amber-950">
        SIMULATED SCREEN: a stand-in for the FeedMe till, with made-up sales. It is not connected to the real FeedMe.
      </div>
      <header className="flex items-center justify-between border-b border-stone-300 bg-white px-4 py-3">
        <span className="text-lg font-semibold text-stone-800">POS · Sales reports</span>
        <Link to="/dashboard" className="text-sm font-medium text-emerald-700 underline">← Back to RestockIQ</Link>
      </header>

      <main className="mx-auto max-w-5xl space-y-4 p-4 md:p-6">
        {!allowed && me.data ? (
          <EmptyState title="Only managers and the owner can export sales" hint="Go back and sign in as Siti or Ah Hock." />
        ) : days.isLoading ? (
          <p className="text-sm text-stone-500">Loading…</p>
        ) : days.error ? (
          <EmptyState title="Could not load the sales reports" hint={days.error.message} />
        ) : (
          <>
            <section className="rounded-xl border border-stone-300 bg-white p-4">
              <h1 className="text-base font-semibold">Daily sales (latest days)</h1>
              <table className="mt-3 w-full text-left text-sm">
                <thead className="border-b border-stone-200 text-xs uppercase text-stone-500">
                  <tr><th className="py-2">Day</th><th>Dishes sold</th><th>Net sales</th><th>In RestockIQ?</th></tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {list.map((d) => (
                    <tr key={d.date}>
                      <td className="py-2">{fmtDay(d.date)}</td>
                      <td>{num(d.dishes, 0)}</td>
                      <td>{rm(d.net_sales_rm)}</td>
                      <td>{d.imported ? <Badge tone="good">Yes</Badge> : <Badge tone="warn">Not sent yet</Badge>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            <section className="rounded-xl border border-stone-300 bg-white p-4">
              <h2 className="text-base font-semibold">Export sales</h2>
              <p className="mt-1 text-sm text-stone-600">Choose the days, download the file, then upload it in RestockIQ.</p>
              <div className="mt-3 flex flex-wrap items-end gap-3">
                <label className="text-sm">
                  <span className="mb-1 block font-medium">From</span>
                  <input type="date" value={start} max={newest} onChange={(e) => setFrom(e.target.value)} className={inputCls} />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block font-medium">To</span>
                  <input type="date" value={end} min={start} max={newest} onChange={(e) => setTo(e.target.value)} className={inputCls} />
                </label>
                <Button onClick={download} disabled={busy || !preview.data}>{busy ? 'Preparing…' : 'Download CSV'}</Button>
              </div>

              {preview.error && <p className="mt-3 text-sm text-red-700">{preview.error.message}</p>}
              {preview.data && (
                <div className="mt-4">
                  <p className="text-xs text-stone-500">
                    Preview: first {preview.data.rows.length} of {num(preview.data.total_rows, 0)} rows
                  </p>
                  <div className="mt-1 overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-stone-200 uppercase text-stone-500">
                        <tr>{preview.data.columns.map((c) => <th key={c} className="px-2 py-1 font-medium">{c}</th>)}</tr>
                      </thead>
                      <tbody className="divide-y divide-stone-100">
                        {preview.data.rows.map((r, i) => (
                          <tr key={i}>{r.map((cell, j) => <td key={j} className="whitespace-nowrap px-2 py-1">{cell}</td>)}</tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  )
}
