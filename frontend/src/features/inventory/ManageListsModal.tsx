import { useState } from 'react'
import { Button, Modal, useToast } from '../../components/ui'
import { useMe } from '../auth/api'
import {
  useAddStorageArea,
  useAddSupplier,
  useRemoveStorageArea,
  useRemoveSupplier,
  useRenameStorageArea,
  useRenameSupplier,
  useStorageAreas,
  useSuppliers,
} from './api'
import { inputCls } from './QtyInput'

type Entry = { id: string; name: string; items: number }

/**
 * One editable list: rename a row and press Save, remove a row (owner only), or type a new name at the bottom
 * and press Add. Removing a row that still has items asks where to move them first.
 */
function NameList({
  title, hint, entries, noun, canRemove, onAdd, onRename, onRemove,
}: {
  title: string
  hint: string
  entries: Entry[]
  noun: string
  canRemove: boolean
  onAdd: (name: string) => Promise<void>
  onRename: (id: string, name: string) => Promise<void>
  onRemove: (id: string, moveTo: string | null) => Promise<string>
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [adding, setAdding] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [removing, setRemoving] = useState<string | null>(null)
  const [moveTo, setMoveTo] = useState('')
  const toast = useToast()

  async function run(key: string, job: () => Promise<string | void>, done: string) {
    setBusy(key)
    try {
      const message = await job()
      toast(message || done, 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Something went wrong', 'error')
    } finally {
      setBusy(null)
    }
  }

  const removingEntry = entries.find((e) => e.id === removing)
  const others = entries.filter((e) => e.id !== removing)

  return (
    <section>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mb-2 text-xs text-slate-500">{hint}</p>
      <ul className="space-y-2">
        {entries.map((e) => {
          const value = drafts[e.id] ?? e.name
          const changed = value.trim() !== '' && value.trim() !== e.name
          return (
            <li key={e.id}>
              <div className="flex gap-2">
                <input
                  aria-label={`${noun} name`}
                  value={value}
                  maxLength={120}
                  onChange={(ev) => setDrafts((d) => ({ ...d, [e.id]: ev.target.value }))}
                  className={`${inputCls} min-w-0 flex-1`}
                />
                <Button
                  variant="secondary"
                  disabled={!changed || busy === e.id}
                  onClick={() =>
                    run(e.id, async () => {
                      await onRename(e.id, value)
                      setDrafts((d) => {
                        const { [e.id]: _gone, ...rest } = d
                        return rest
                      })
                    }, `${noun} renamed`)
                  }
                >
                  {busy === e.id ? 'Saving…' : 'Save'}
                </Button>
                {canRemove && (
                  <Button variant="ghost" aria-label={`Remove ${e.name}`} onClick={() => { setRemoving(e.id); setMoveTo('') }}>
                    Remove
                  </Button>
                )}
              </div>
              {removing === e.id && removingEntry && (
                <div className="mt-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm">
                  <p className="font-medium text-red-900">Remove {removingEntry.name}?</p>
                  {removingEntry.items > 0 ? (
                    <label className="mt-2 block">
                      <span className="mb-1 block text-red-900">
                        {removingEntry.items} item{removingEntry.items === 1 ? '' : 's'} use{removingEntry.items === 1 ? 's' : ''} it. Move {removingEntry.items === 1 ? 'it' : 'them'} to:
                      </span>
                      <select aria-label={`Move items to`} value={moveTo} onChange={(ev) => setMoveTo(ev.target.value)} className={`${inputCls} w-full`}>
                        <option value="">Choose a {noun}</option>
                        {others.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
                      </select>
                    </label>
                  ) : (
                    <p className="mt-1 text-red-900">Nothing uses it, so nothing needs to move.</p>
                  )}
                  <div className="mt-3 flex justify-end gap-2">
                    <Button variant="secondary" onClick={() => setRemoving(null)}>Cancel</Button>
                    <Button
                      variant="danger"
                      disabled={(removingEntry.items > 0 && !moveTo) || busy === `rm-${e.id}`}
                      onClick={() => run(`rm-${e.id}`, async () => {
                        const message = await onRemove(e.id, removingEntry.items > 0 ? moveTo : null)
                        setRemoving(null)
                        return message
                      }, `${noun} removed`)}
                    >
                      {busy === `rm-${e.id}` ? 'Removing…' : `Remove ${noun}`}
                    </Button>
                  </div>
                </div>
              )}
            </li>
          )
        })}
      </ul>
      <form
        className="mt-2 flex gap-2"
        onSubmit={(ev) => {
          ev.preventDefault()
          if (!adding.trim()) return
          void run('new', async () => { await onAdd(adding); setAdding('') }, `${noun} added`)
        }}
      >
        <input
          aria-label={`New ${noun} name`}
          value={adding}
          maxLength={120}
          onChange={(ev) => setAdding(ev.target.value)}
          placeholder={`New ${noun} name`}
          className={`${inputCls} min-w-0 flex-1`}
        />
        <Button type="submit" disabled={!adding.trim() || busy === 'new'}>
          {busy === 'new' ? 'Adding…' : 'Add'}
        </Button>
      </form>
    </section>
  )
}

const movedText = (r: { removed: string; moved_items: number; moved_to: string | null }) =>
  r.moved_items > 0 ? `${r.removed} removed. ${r.moved_items} item${r.moved_items === 1 ? '' : 's'} moved to ${r.moved_to}.` : `${r.removed} removed.`

/** Add, rename and (owner only) remove suppliers and storage places. Used from the Add item form and the Inventory page. */
export default function ManageListsModal({
  open, onClose, onCreated,
}: {
  open: boolean
  onClose: () => void
  /** Called after something new is added, so the form that opened this can select it. */
  onCreated?: (kind: 'supplier' | 'place', id: string) => void
}) {
  const me = useMe()
  const suppliers = useSuppliers()
  const areas = useStorageAreas()
  const addSupplier = useAddSupplier()
  const renameSupplier = useRenameSupplier()
  const removeSupplier = useRemoveSupplier()
  const addArea = useAddStorageArea()
  const renameArea = useRenameStorageArea()
  const removeArea = useRemoveStorageArea()
  const isOwner = me.data?.role === 'owner'

  return (
    <Modal open={open} title="Suppliers and storage places" onClose={onClose}>
      <div className="space-y-5">
        <NameList
          title="Suppliers"
          noun="supplier"
          hint="Who you buy from. Their WhatsApp number and minimum order are set later under Plan purchases, Supplier details."
          entries={(suppliers.data ?? []).map((s) => ({ id: String(s.id), name: s.name, items: s.items }))}
          canRemove={isOwner}
          onAdd={async (name) => {
            const s = await addSupplier.mutateAsync(name)
            onCreated?.('supplier', String(s.id))
          }}
          onRename={async (id, name) => { await renameSupplier.mutateAsync({ id: Number(id), name }) }}
          onRemove={async (id, moveTo) => movedText(await removeSupplier.mutateAsync({ id: Number(id), moveTo }))}
        />
        <NameList
          title="Where it is kept"
          noun="place"
          hint="Freezer, chiller, dry store or your own, such as a back shelf. Renaming keeps all the items in it."
          entries={(areas.data ?? []).map((a) => ({ id: a.key, name: a.name, items: a.items }))}
          canRemove={isOwner}
          onAdd={async (name) => {
            const a = await addArea.mutateAsync(name)
            onCreated?.('place', a.key)
          }}
          onRename={async (key, name) => { await renameArea.mutateAsync({ key, name }) }}
          onRemove={async (key, moveTo) => movedText(await removeArea.mutateAsync({ key, moveTo }))}
        />
        {!isOwner && <p className="text-xs text-slate-500">Only the owner can remove a supplier or a place.</p>}
        <div className="flex justify-end">
          <Button variant="secondary" onClick={onClose}>Done</Button>
        </div>
      </div>
    </Modal>
  )
}
