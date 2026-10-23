import { useState } from 'react'
import { Badge, Button, Modal, useToast } from '../../components/ui'
import { fmtDay, num, rm } from '../planning/format'
import { useImportSales, usePreviewImport, type ImportSummary } from './api'

/** Upload a sales CSV exported from the POS, see exactly what it contains, then confirm. */
export default function ImportSalesModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const preview = usePreviewImport()
  const save = useImportSales()
  const toast = useToast()
  const [file, setFile] = useState<{ name: string; text: string } | null>(null)
  const [summary, setSummary] = useState<ImportSummary | null>(null)

  function close() {
    setFile(null)
    setSummary(null)
    preview.reset()
    onClose()
  }

  async function pick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    setSummary(null)
    preview.reset()
    if (!f) return setFile(null)
    const text = await f.text()
    setFile({ name: f.name, text })
    try {
      setSummary(await preview.mutateAsync(text))
    } catch {
      /* the error is shown below from preview.error */
    }
  }

  async function confirm() {
    if (!file) return
    try {
      const s = await save.mutateAsync({ filename: file.name, csvText: file.text })
      toast(`Imported ${s.days} day${s.days === 1 ? '' : 's'} of sales (${num(s.dishes_sold, 0)} dishes).`, 'success')
      close()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not import', 'error')
    }
  }

  return (
    <Modal open={open} title="Import sales from your POS" onClose={close}>
      <div className="space-y-3 text-sm">
        <p className="text-slate-600">
          Choose the CSV file you exported from FeedMe. Nothing is saved until you press Import.
        </p>
        <input type="file" accept=".csv,text/csv" onChange={pick} className="block w-full text-sm" />

        {preview.isPending && <p className="text-slate-500">Reading the file…</p>}
        {preview.error && <p className="rounded-lg bg-red-50 p-3 text-red-800">{preview.error.message}</p>}

        {summary && (
          <div className="space-y-3">
            <div className="rounded-lg border border-slate-200 p-3">
              {summary.rows_ok === 0 ? (
                <p className="font-medium text-red-800">Nothing in this file can be imported.</p>
              ) : (
                <>
                  <p className="font-medium">
                    {summary.days} day{summary.days === 1 ? '' : 's'}: {fmtDay(summary.date_from!)}
                    {summary.date_from !== summary.date_to && <> to {fmtDay(summary.date_to!)}</>}
                  </p>
                  <p className="mt-1 text-slate-600">
                    {num(summary.dishes_sold, 0)} dishes sold · {rm(summary.net_sales_rm)} in sales
                  </p>
                  <p className="mt-1 flex flex-wrap gap-2">
                    {summary.new_days > 0 && <Badge tone="good">{summary.new_days} new day{summary.new_days === 1 ? '' : 's'}</Badge>}
                    {summary.replaced_days > 0 && (
                      <Badge tone="warn">{summary.replaced_days} day{summary.replaced_days === 1 ? '' : 's'} already here will be replaced</Badge>
                    )}
                  </p>
                </>
              )}
            </div>

            {summary.unmatched.length > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-900">
                <p className="font-medium">Not on your menu, so left out:</p>
                <ul className="mt-1 list-disc pl-5">
                  {summary.unmatched.map((u) => <li key={u.name}>{u.name} ({u.rows} row{u.rows === 1 ? '' : 's'})</li>)}
                </ul>
                <p className="mt-1 text-xs">We do not guess. Add these dishes to your menu first if you want them counted.</p>
              </div>
            )}

            {summary.bad_count > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-900">
                <p className="font-medium">{summary.bad_count} row{summary.bad_count === 1 ? '' : 's'} skipped:</p>
                <ul className="mt-1 list-disc pl-5">
                  {summary.bad_rows.map((b) => <li key={b.line}>Line {b.line}: {b.reason}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={close}>Cancel</Button>
          <Button onClick={confirm} disabled={!summary || summary.rows_ok === 0 || save.isPending}>
            {save.isPending ? 'Importing…' : 'Import'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
