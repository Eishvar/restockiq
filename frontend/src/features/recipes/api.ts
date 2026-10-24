import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

export type RecipeLine = { ingredient_id: number; ingredient_name: string; qty_per_serving: number; base_uom: string }

export type Dish = {
  id: number
  code: string
  name: string
  category: string
  price_rm: number
  has_recipe: boolean
  lines: RecipeLine[]
}

/** What the server needs for one line: the ingredient and the amount in one serving (in g, ml or pcs). */
export type LineInput = { ingredient_id: number; qty_per_serving: number }

export type NewDish = { name: string; category: string; price_rm: number; lines: LineInput[] }

export type IngredientOption = { id: number; name: string; base_uom: string; active: boolean }

export const useRecipeBook = () => useQuery({ queryKey: ['recipes'], queryFn: () => api<Dish[]>('/catalog/recipe-book') })

export const useIngredientOptions = () =>
  useQuery({
    queryKey: ['ingredient-options'],
    queryFn: () => api<IngredientOption[]>('/catalog/ingredients'),
    staleTime: 30_000,
  })

/** A recipe change affects the next plan, the activity log and the setup wizard's "dishes missing a recipe" check. */
function useRecipeWrite<TVars>(fn: (v: TVars) => Promise<Dish>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      for (const key of ['recipes', 'activity', 'setup', 'planning']) qc.invalidateQueries({ queryKey: [key] })
    },
  })
}

export const useSaveRecipe = () =>
  useRecipeWrite(({ id, lines }: { id: number; lines: LineInput[] }) =>
    api<Dish>(`/catalog/menu/${id}/recipe`, { method: 'PUT', body: JSON.stringify({ lines }) }),
  )

export const useAddDish = () =>
  useRecipeWrite((dish: NewDish) => api<Dish>('/catalog/menu', { method: 'POST', body: JSON.stringify(dish) }))
