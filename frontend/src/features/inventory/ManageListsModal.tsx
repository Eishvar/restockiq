import { useState } from 'react'
import { Button, Modal, useToast } from '../../components/ui'
import {
  useAddStorageArea,
  useAddSupplier,
  useRenameStorageArea,
  useRenameSupplier,
  useStorageAreas,
  useSuppliers,
} from './api'
import { inputCls } from './QtyInput'

type Entry = { id: string; name: string }

/** One editable list: rename a row and press Save, or type a new name at the bottom and press Add. */
function NameList({
  title, hint, entries, noun, onAdd, onRename,
}: {
  title: string
  hint: string
  entries: Entry[]
  noun: string
  onAdd: (name: string) => Promise<void>
  onRename: (id: string, name: string) => Promise<void>
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [adding, setAdding] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const toast = useToast()

  async function run(key: string, job: () => Promise<void>, done: string) {
    setBusy(key)
    try {
      await job()
      toast(done, 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Something went wrong', 'error')
    } finally {
      setBusy(null)
    }
  }

  return (
    <section>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mb-2 text-xs text-slate-500">{hint}</p>
      <ul className="space-y-2">
        {entries.map((e) => {
          const value = drafts[e.id] ?? e.name
          const changed = value.trim() !== '' && value.trim() !== e.name
          return (
            <li key={e.id} className="flex gap-2">
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

/** Add or rename suppliers and storage places. Used from the Add item form and the Inventory page. */
export default function ManageListsModal({
  open, onClose, onCreated,
}: {
  open: boolean
  onClose: () => void
  /** Called after something new is added, so the form that opened this can select it. */
  onCreated?: (kind: 'supplier' | 'place', id: string) => void
}) {
  const suppliers = useSuppliers()
  const areas = useStorageAreas()
  const addSupplier = useAddSupplier()
  const renameSupplier = useRenameSupplier()
  const addArea = useAddStorageArea()
  const renameArea = useRenameStorageArea()

  return (
    <Modal open={open} title="Suppliers and storage places" onClose={onClose}>
      <div className="space-y-5">
        <NameList
          title="Suppliers"
          noun="supplier"
          hint="Who you buy from. Their WhatsApp number and minimum order are set later under Plan purchases, Supplier details."
          entries={(suppliers.data ?? []).map((s) => ({ id: String(s.id), name: s.name }))}
          onAdd={async (name) => {
            const s = await addSupplier.mutateAsync(name)
            onCreated?.('supplier', String(s.id))
          }}
          onRename={async (id, name) => { await renameSupplier.mutateAsync({ id: Number(id), name }) }}
        />
        <NameList
          title="Where it is kept"
          noun="place"
          hint="Freezer, chiller, dry store or your own, such as a back shelf. Renaming keeps all the items in it."
          entries={(areas.data ?? []).map((a) => ({ id: a.key, name: a.name }))}
          onAdd={async (name) => {
            const a = await addArea.mutateAsync(name)
            onCreated?.('place', a.key)
          }}
          onRename={async (key, name) => { await renameArea.mutateAsync({ key, name }) }}
        />
        <div className="flex justify-end">
          <Button variant="secondary" onClick={onClose}>Done</Button>
        </div>
      </div>
    </Modal>
  )
}
