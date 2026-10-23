import { useState } from 'react'
import { ApiError } from '../../api/client'
import { Badge, Button, Modal, useToast } from '../../components/ui'
import type { InventoryList } from '../inventory/api'
import QtyInput, { inputCls } from '../inventory/QtyInput'
import { formatQty } from '../planning/format'
import GatedButton, { useRole } from '../planning/GatedButton'
import { UNAVAILABLE_TEXT, useAiStatus, useApplyNote, useReadNote, type Confidence, type NoteResult } from './api'

const TONE: Record<Confidence, 'good' | 'warn' | 'bad'> = { high: 'good', medium: 'warn', low: 'bad' }
const EXAMPLE = 'beras 12 bag, telur 3 tray beli semalam, ayam 2 ctn isnin'

type Draft = {
  ingredient_id: number | null
  qty_base: number | null
  last_purchased_on: string | null
  include: boolean
}

function Unavailable() {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="alert">
      <strong>{UNAVAILABLE_TEXT}.</strong> The AI helper is not reachable right now. You can still update stock by hand on this page: use Edit
      on an item, or + Add item.
    </div>
  )
}

/** Paste a messy stock note, check what the AI understood, then save. Nothing is saved until you press Save. */
export default function QuickNoteModal({ open, onClose, data }: { open: boolean; onClose: () => void; data: InventoryList }) {
  const status = useAiStatus()
  const read = useReadNote()
  const apply = useApplyNote()
  const toast = useToast()
  const { isManager } = useRole()
  const [note, setNote] = useState('')
  const [result, setResult] = useState<NoteResult | null>(null)
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [failed, setFailed] = useState(false)

  const items = [...data.items].sort((a, b) => a.name.localeCompare(b.name))
  const byId = new Map(data.items.map((i) => [i.ingredient_id, i]))
  const aiOff = status.data?.available === false || failed

  function close() {
    setResult(null)
    setFailed(false)
    onClose()
  }

  async function readNote() {
    setFailed(false)
    try {
      const res = await read.mutateAsync(note)
      setResult(res)
      setDrafts(
        res.rows.map((r) => ({
          ingredient_id: r.ingredient_id,
          qty_base: r.qty_base,
          last_purchased_on: r.last_purchased_on,
          include: r.ingredient_id !== null && r.qty_base !== null,
        })),
      )
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) setFailed(true)
      else toast(err instanceof Error ? err.message : 'Could not read the note', 'error')
    }
  }

  const change = (i: number, patch: Partial<Draft>) => setDrafts((d) => d.map((x, n) => (n === i ? { ...x, ...patch } : x)))
  const chosen = drafts.filter((d) => d.include && d.ingredient_id !== null && d.qty_base !== null)
  const duplicate = new Set(chosen.map((d) => d.ingredient_id)).size !== chosen.length

  async function save() {
    if (!result) return
    try {
      const r = await apply.mutateAsync({
        id: result.suggestion_id,
        rows: chosen.map((d) => ({ ingredient_id: d.ingredient_id!, qty_base: d.qty_base!, last_purchased_on: d.last_purchased_on })),
      })
      toast(`Stock updated for ${r.applied} item${r.applied === 1 ? '' : 's'}`, 'success')
      setNote('')
      close()
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not save', 'error')
    }
  }

  return (
    <Modal open={open} title="Quick add from a note" onClose={close}>
      {!result ? (
        <div className="space-y-3">
          <p className="text-sm text-slate-600">
            Type or paste what you have, in English or Bahasa Malaysia. We read it, and you check it before anything is saved.
          </p>
          {aiOff && <Unavailable />}
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={4}
            maxLength={2000}
            placeholder={`e.g. ${EXAMPLE}`}
            aria-label="Stock note"
            className={`${inputCls} w-full`}
          />
          <button type="button" className="text-xs text-emerald-700 underline" onClick={() => setNote(EXAMPLE)}>
            Use the example
          </button>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={close}>Cancel</Button>
            <Button onClick={readNote} disabled={!note.trim() || read.isPending || status.data?.available === false}>
              {read.isPending ? 'Reading…' : 'Read my note'}
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-slate-600">
            Check each line. The amount you wrote becomes your stock for that item. Untick a line to skip it.
          </p>
          <div className="max-h-[55vh] space-y-3 overflow-y-auto">
            {result.rows.map((r, i) => {
              const d = drafts[i]
              const item = d.ingredient_id !== null ? byId.get(d.ingredient_id) : undefined
              return (
                <div key={r.index} className="rounded-lg border border-slate-200 p-3 text-sm">
                  <div className="flex items-start justify-between gap-2">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={d.include}
                        disabled={d.ingredient_id === null || d.qty_base === null}
                        onChange={(e) => change(i, { include: e.target.checked })}
                        aria-label={`Include ${r.raw_text}`}
                      />
                      <span className="text-slate-500">You wrote: “{r.raw_text}”</span>
                    </label>
                    <Badge tone={TONE[r.confidence]}>{r.confidence === 'high' ? 'Sure' : r.confidence === 'medium' ? 'Check this' : 'Not sure'}</Badge>
                  </div>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    <label className="block">
                      <span className="mb-1 block text-xs text-slate-500">Item</span>
                      <select
                        value={d.ingredient_id ?? ''}
                        onChange={(e) => {
                          const id = e.target.value ? Number(e.target.value) : null
                          change(i, { ingredient_id: id, include: id !== null && d.qty_base !== null })
                        }}
                        className={`${inputCls} w-full`}
                        aria-label="Item"
                      >
                        <option value="">{r.new_item_name ? `Not in my list: ${r.new_item_name}` : 'Not in my list'}</option>
                        {items.map((it) => (
                          <option key={it.ingredient_id} value={it.ingredient_id}>{it.name}</option>
                        ))}
                      </select>
                    </label>
                    <div>
                      <span className="mb-1 block text-xs text-slate-500">Amount in stock after saving</span>
                      {item ? (
                        <QtyInput
                          key={item.ingredient_id}
                          baseQty={d.qty_base ?? 0}
                          item={item}
                          onChange={(q) => change(i, { qty_base: q, include: true })}
                        />
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                      {item && <span className="mt-1 block text-xs text-slate-500">Now: {formatQty(item.qty_base, item.base_uom)}</span>}
                    </div>
                    {item && (
                      <label className="block">
                        <span className="mb-1 block text-xs text-slate-500">Last bought</span>
                        <input
                          type="date"
                          max={data.today}
                          value={d.last_purchased_on ?? ''}
                          onChange={(e) => change(i, { last_purchased_on: e.target.value || null })}
                          className={inputCls}
                          aria-label="Last bought"
                        />
                      </label>
                    )}
                  </div>
                  {r.issue && <p className="mt-2 flex items-start gap-1.5 text-xs text-amber-800"><svg aria-hidden="true" className="mt-px shrink-0" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3 2.7 20h18.6L12 3Z"/><path d="M12 9v5m0 3h.01"/></svg>{r.issue}</p>}
                </div>
              )
            })}
          </div>
          {duplicate && <p className="text-sm text-red-700">The same item is ticked twice. Keep one line for each item.</p>}
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={() => setResult(null)}>Start over</Button>
            <GatedButton allowed={isManager} need="manager" verb="save stock from a note" onClick={save} disabled={!chosen.length || duplicate || apply.isPending}>
              {apply.isPending ? 'Saving…' : `Save ${chosen.length} item${chosen.length === 1 ? '' : 's'}`}
            </GatedButton>
          </div>
        </div>
      )}
    </Modal>
  )
}
