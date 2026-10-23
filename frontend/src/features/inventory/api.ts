import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

export type Status = 'ok' | 'expiring_soon' | 'expired'

export type Batch = {
  id: number
  ingredient_id: number
  procured_on: string
  qty_base: number
  display_qty: string
  shelf_life_days: number
  pack_price_rm: number
  value_rm: number
  expires_on: string
  days_left: number
  status: Status
}

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
  expired_qty_base: number
  stock_value_rm: number
  batches: Batch[]
}

export type InventoryList = { today: string; onboarded: boolean; items: InventoryRow[] }

export type ItemPatch = {
  qty_base?: number
  last_purchased_on?: string | null
  shelf_life_days?: number
  pack_price_rm?: number
}

export type BatchPatch = {
  qty_base?: number
  procured_on?: string
  shelf_life_days?: number
  pack_price_rm?: number
}

export type NewBatch = {
  qty_base: number
  procured_on?: string
  shelf_life_days?: number
  pack_price_rm?: number
}

export type DiscardResult = { discarded: string[]; batches: number }

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
    api<DiscardResult>(id === null ? '/inventory/discard-expired' : `/inventory/${id}/discard-expired`, send('POST')),
  )

export const useAddBatch = () =>
  useWrite(({ ingredientId, batch }: { ingredientId: number; batch: NewBatch }) =>
    api<InventoryRow>(`/inventory/${ingredientId}/batches`, send('POST', batch)),
  )

export const usePatchBatch = () =>
  useWrite(({ id, patch }: { id: number; patch: BatchPatch }) => api<InventoryRow>(`/inventory/batches/${id}`, send('PATCH', patch)))

export const useRemoveBatch = () => useWrite((id: number) => api<void>(`/inventory/batches/${id}`, send('DELETE')))

export const useDiscardBatch = () =>
  useWrite((id: number) => api<DiscardResult>(`/inventory/batches/${id}/discard`, send('POST')))

export const useConfirmOnboarding = () =>
  useWrite(() => api<{ onboarded: boolean }>('/inventory/onboarding/confirm', send('POST')))
