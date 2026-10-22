import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

export type Status = 'ok' | 'expiring_soon' | 'expired'

export type InventoryRow = {
  ingredient_id: number
  code: string
  name: string
  storage: 'freezer' | 'chiller' | 'dry'
  supplier_id: number | null
  supplier_name: string | null
  base_uom: string
  pack_uom: string
  pack_size_base: number
  pack_price_rm: number
  qty_base: number
  display_qty: string
  last_purchased_on: string | null
  shelf_life_days: number
  expires_on: string | null
  days_left: number | null
  status: Status
}

export type InventoryList = { today: string; onboarded: boolean; items: InventoryRow[] }

export type ItemPatch = {
  qty_base?: number
  last_purchased_on?: string | null
  shelf_life_days?: number
  pack_price_rm?: number
}

export type NewItem = {
  name: string
  storage: string
  base_uom: string
  supplier_id: number | null
  pack_uom: string
  pack_size_base: number
  pack_price_rm: number
  shelf_life_days: number
  qty_base: number
  last_purchased_on: string | null
  suggestion_id?: number | null
}

export type Movement = {
  id: number
  date: string
  change_base: number
  display_change: string
  reason: string
  user_name: string | null
  note: string
}

export type Supplier = { id: number; code: string; name: string }

export const useInventory = () => useQuery({ queryKey: ['inventory'], queryFn: () => api<InventoryList>('/inventory') })

export const useSuppliers = () => useQuery({ queryKey: ['suppliers'], queryFn: () => api<Supplier[]>('/catalog/suppliers') })

export const useMovements = (ingredientId: number | null) =>
  useQuery({
    queryKey: ['movements', ingredientId],
    queryFn: () => api<Movement[]>(`/inventory/${ingredientId}/movements`),
    enabled: ingredientId !== null,
  })

/** Runs a write, then refreshes stock, the activity log and any open history. */
function useWrite<TVars, TOut>(fn: (v: TVars) => Promise<TOut>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      qc.invalidateQueries({ queryKey: ['activity'] })
      qc.invalidateQueries({ queryKey: ['movements'] })
    },
  })
}

const send = (method: string, body?: unknown) => ({ method, body: body === undefined ? undefined : JSON.stringify(body) })

export const usePatchItem = () =>
  useWrite(({ id, patch }: { id: number; patch: ItemPatch }) =>
    api<InventoryRow>(`/inventory/${id}`, send('PATCH', patch)),
  )

export const useAddItem = () => useWrite((item: NewItem) => api<InventoryRow>('/inventory/items', send('POST', item)))

export const useRemoveItem = () =>
  useWrite((id: number) => api<void>(`/inventory/${id}`, send('DELETE')))

export const useDiscardExpired = () =>
  useWrite((id: number | null) =>
    api<{ discarded: string[] }>(id === null ? '/inventory/discard-expired' : `/inventory/${id}/discard-expired`, send('POST')),
  )

export const useConfirmOnboarding = () =>
  useWrite(() => api<{ onboarded: boolean }>('/inventory/onboarding/confirm', send('POST')))
