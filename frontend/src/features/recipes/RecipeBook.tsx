import { useMemo, useState } from 'react'
import { Badge, Button, Card, EmptyState, Modal, PageSkeleton, useToast } from '../../components/ui'
import { inputCls } from '../inventory/QtyInput'
import GatedButton, { useRole } from '../planning/GatedButton'
import {
  useAddDish, useIngredientOptions, useRecipeBook, useSaveRecipe,
  type Dish, type IngredientOption, type LineInput,
} from './api'

/** One row being edited. `qty` stays text so half-typed numbers like "1." are allowed. */
type Draft = { key: number; ingredient_id: number | ''; qty: string }

let nextKey = 1
const blankRow = (): Draft => ({ key: nextKey++, ingredient_id: '', qty: '' })
const draftFrom = (dish: Dish): Draft[] =>
  dish.lines.length
    ? dish.lines.map((l) => ({ key: nextKey++, ingredient_id: l.ingredient_id, qty: String(l.qty_per_serving) }))
    : [blankRow()]

const fmt = (n: number) => String(Number(n.toFixed(4)))

/** Turns the rows into what the server wants, or says in plain words what is wrong. */
function check(rows: Draft[]): { lines: LineInput[] } | { error: string } {
  const filled = rows.filter((r) => r.ingredient_id !== '' || r.qty.trim() !== '')
  if (!filled.length) return { error: 'Add at least one ingredient.' }
  const lines: LineInput[] = []
  for (const r of filled) {
    const qty = Number(r.qty)
    if (r.ingredient_id === '') return { error: 'Choose an ingredient for every row.' }
    if (!r.qty.trim() || !Number.isFinite(qty) || qty <= 0) return { error: 'Type an amount above 0 for every ingredient.' }
    lines.push({ ingredient_id: r.ingredient_id, qty_per_serving: qty })
  }
  if (new Set(lines.map((l) => l.ingredient_id)).size !== lines.length) return { error: 'Each ingredient can only appear once.' }
  return { lines }
}

function LinesEditor({ rows, setRows, options }: { rows: Draft[]; setRows: (r: Draft[]) => void; options: IngredientOption[] }) {
  const set = (key: number, change: Partial<Draft>) => setRows(rows.map((r) => (r.key === key ? { ...r, ...change } : r)))
  const used = new Set(rows.map((r) => r.ingredient_id))
  return (
    <div className="space-y-2">
      {rows.map((r) => {
        const unit = options.find((o) => o.id === r.ingredient_id)?.base_uom
        return (
          <div key={r.key} className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Ingredient"
              value={r.ingredient_id}
              onChange={(e) => set(r.key, { ingredient_id: e.target.value ? Number(e.target.value) : '' })}
              className={`${inputCls} min-w-0 flex-1 basis-40`}
            >
              <option value="">Choose an ingredient…</option>
              {options.map((o) => (
                <option key={o.id} value={o.id} disabled={used.has(o.id) && o.id !== r.ingredient_id}>{o.name}</option>
              ))}
            </select>
            <input
              type="number"
              inputMode="decimal"
              min={0}
              step="any"
              aria-label="Amount in one serving"
              placeholder="Amount"
              value={r.qty}
              onChange={(e) => set(r.key, { qty: e.target.value })}
              className={`${inputCls} w-24`}
            />
            <span className="w-10 text-sm text-slate-600">{unit ?? ''}</span>
            <button
              type="button"
              aria-label="Remove this ingredient"
              onClick={() => setRows(rows.length > 1 ? rows.filter((x) => x.key !== r.key) : [blankRow()])}
              className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-red-700"
            >
              <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m6 6 12 12M18 6 6 18" /></svg>
            </button>
          </div>
        )
      })}
      <Button type="button" variant="ghost" onClick={() => setRows([...rows, blankRow()])}>+ Add an ingredient</Button>
    </div>
  )
}

function DishRow({ dish, options, canEdit, open, onToggle }: {
  dish: Dish; options: IngredientOption[]; canEdit: boolean; open: boolean; onToggle: () => void
}) {
  const [rows, setRows] = useState<Draft[]>(() => draftFrom(dish))
  const save = useSaveRecipe()
  const toast = useToast()
  const [error, setError] = useState('')
  const summary = dish.lines.map((l) => `${l.ingredient_name} ${fmt(l.qty_per_serving)} ${l.base_uom}`).join(', ')

  function toggle() {
    if (!open) { setRows(draftFrom(dish)); setError('') }
    onToggle()
  }

  async function submit() {
    const result = check(rows)
    if ('error' in result) { setError(result.error); return }
    setError('')
    try {
      await save.mutateAsync({ id: dish.id, lines: result.lines })
      toast(`Recipe for ${dish.name} saved. It is used the next time you generate a plan.`, 'success')
      onToggle()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the recipe')
    }
  }

  return (
    <li className={open ? 'bg-brand-surface/60' : ''}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2.5">
        <div className="min-w-0 flex-1 basis-56">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{dish.name}</span>
            <span className="text-xs text-slate-500">{dish.category}</span>
            {!dish.has_recipe && <Badge tone="warn">No recipe yet</Badge>}
          </div>
          {!open && <p className="mt-0.5 truncate text-xs text-slate-500" title={summary}>{summary || 'Add the ingredients that go into one serving.'}</p>}
        </div>
        <Button variant={dish.has_recipe ? 'secondary' : 'primary'} onClick={toggle} aria-expanded={open}>
          {open ? 'Close' : canEdit ? (dish.has_recipe ? 'Edit' : 'Add recipe') : 'View'}
        </Button>
      </div>

      {open && (
        <div className="border-t border-slate-100 px-3 pb-4 pt-3">
          {canEdit ? (
            <>
              <p className="mb-2 text-xs text-slate-600">Ingredients in <strong>one serving</strong> of {dish.name}, in grams (g), millilitres (ml) or pieces (pcs).</p>
              <LinesEditor rows={rows} setRows={setRows} options={options} />
              {error && <p role="alert" className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
              <div className="mt-3 flex justify-end gap-2">
                <Button variant="secondary" onClick={onToggle} disabled={save.isPending}>Cancel</Button>
                <Button onClick={submit} disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save recipe'}</Button>
              </div>
            </>
          ) : (
            <ul className="space-y-1 text-sm">
              {dish.lines.map((l) => <li key={l.ingredient_id}>{l.ingredient_name}: {fmt(l.qty_per_serving)} {l.base_uom}</li>)}
              {!dish.lines.length && <li className="text-slate-500">No recipe yet. A manager or the owner can add one.</li>}
            </ul>
          )}
        </div>
      )}
    </li>
  )
}

function AddDishModal({ open, onClose, categories, options }: {
  open: boolean; onClose: () => void; categories: string[]; options: IngredientOption[]
}) {
  const add = useAddDish()
  const toast = useToast()
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [price, setPrice] = useState('')
  const [rows, setRows] = useState<Draft[]>(() => [blankRow()])
  const [error, setError] = useState('')

  function close() {
    setName(''); setCategory(''); setPrice(''); setRows([blankRow()]); setError('')
    onClose()
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const result = check(rows)
    if ('error' in result) { setError(result.error); return }
    try {
      await add.mutateAsync({ name: name.trim(), category: category.trim(), price_rm: Number(price) || 0, lines: result.lines })
      toast(`${name.trim()} added. Include it in your next sales file so the forecast can learn it.`, 'success')
      close()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add the dish')
    }
  }

  return (
    <Modal open={open} title="Add a dish" onClose={close}>
      <form onSubmit={submit} className="space-y-3">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Dish name</span>
          <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Nasi Lemak Ayam" className={`${inputCls} w-full`} />
          <span className="mt-1 block text-xs text-slate-500">Use the same name your sales system prints, so the sales file matches it.</span>
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Category</span>
            <input required list="dish-categories" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="e.g. Rice" className={`${inputCls} w-full`} />
            <datalist id="dish-categories">{categories.map((c) => <option key={c} value={c} />)}</datalist>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Selling price (RM)</span>
            <input type="number" min={0} step="0.1" value={price} onChange={(e) => setPrice(e.target.value)} className={`${inputCls} w-full`} />
          </label>
        </div>
        <div>
          <span className="mb-1 block text-sm font-medium">Ingredients in one serving</span>
          <LinesEditor rows={rows} setRows={setRows} options={options} />
        </div>
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={close} disabled={add.isPending}>Cancel</Button>
          <Button type="submit" disabled={add.isPending || !name.trim() || !category.trim()}>{add.isPending ? 'Adding…' : 'Add dish'}</Button>
        </div>
      </form>
    </Modal>
  )
}

/** Every dish with its recipe: search, find the ones still missing a recipe, edit, or add a dish. */
export default function RecipeBook() {
  const book = useRecipeBook()
  const ingredients = useIngredientOptions()
  const { isManager } = useRole()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [missingOnly, setMissingOnly] = useState(false)
  const [openId, setOpenId] = useState<number | null>(null)
  const [adding, setAdding] = useState(false)

  const dishes = useMemo(() => book.data ?? [], [book.data])
  const options = useMemo(
    () => (ingredients.data ?? []).filter((i) => i.active).sort((a, b) => a.name.localeCompare(b.name)),
    [ingredients.data],
  )
  const categories = useMemo(() => Array.from(new Set(dishes.map((d) => d.category))).sort(), [dishes])
  const missing = dishes.filter((d) => !d.has_recipe).length
  const shown = dishes.filter(
    (d) =>
      (!missingOnly || !d.has_recipe) &&
      (!category || d.category === category) &&
      d.name.toLowerCase().includes(search.trim().toLowerCase()),
  )

  if (book.isLoading || ingredients.isLoading) return <PageSkeleton rows={2} />
  if (book.error || !book.data) return <EmptyState title="Could not load the recipes" hint={book.error?.message} />

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-700">
          <strong>{dishes.length}</strong> dishes
          {missing > 0
            ? <> · <span className="font-medium text-amber-800">{missing} still {missing === 1 ? 'needs' : 'need'} a recipe</span></>
            : <> · every dish has a recipe</>}
        </p>
        <GatedButton allowed={isManager} need="manager" verb="add a dish" onClick={() => setAdding(true)}>+ Add a dish</GatedButton>
      </div>

      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input
            type="search"
            aria-label="Search dishes"
            placeholder="Search dishes…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={`${inputCls} min-w-0 flex-1 basis-48`}
          />
          <select aria-label="Category" value={category} onChange={(e) => setCategory(e.target.value)} className={inputCls}>
            <option value="">All categories</option>
            {categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={missingOnly} onChange={(e) => setMissingOnly(e.target.checked)} />
            Only dishes without a recipe
          </label>
        </div>

        {shown.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">
            {missingOnly && !search && !category ? 'Every dish has a recipe.' : 'No dishes match.'}
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {shown.map((d) => (
              <DishRow
                key={d.id}
                dish={d}
                options={options}
                canEdit={isManager}
                open={openId === d.id}
                onToggle={() => setOpenId(openId === d.id ? null : d.id)}
              />
            ))}
          </ul>
        )}
      </Card>

      <AddDishModal open={adding} onClose={() => setAdding(false)} categories={categories} options={options} />
    </div>
  )
}
