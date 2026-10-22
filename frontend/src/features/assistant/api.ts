import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

export type Confidence = 'high' | 'medium' | 'low'

export type ReviewRow = {
  index: number
  ingredient_id: number | null
  ingredient_name: string | null
  new_item_name: string | null
  raw_text: string
  qty: number | null
  unit: string | null
  qty_base: number | null
  last_purchased_on: string | null
  confidence: Confidence
  issue: string | null
  current_qty_base: number | null
}

export type NoteResult = { suggestion_id: number; model: string; rows: ReviewRow[] }

export type ShelfLifeSuggestion = {
  suggestion_id: number
  shelf_life_days: number
  storage: 'freezer' | 'chiller' | 'dry'
  base_uom: 'g' | 'ml' | 'pcs'
  rationale: string
}

export const UNAVAILABLE_TEXT = 'AI unavailable, enter manually'

export const useAiStatus = () =>
  useQuery({ queryKey: ['ai-status'], queryFn: () => api<{ available: boolean }>('/assistant/status'), staleTime: 60_000 })

export const useReadNote = () =>
  useMutation({
    mutationFn: (note: string) => api<NoteResult>('/assistant/stock-note', { method: 'POST', body: JSON.stringify({ note }) }),
  })

export const useApplyNote = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, rows }: { id: number; rows: { ingredient_id: number; qty_base: number; last_purchased_on: string | null }[] }) =>
      api<{ applied: number; items: string[] }>(`/assistant/suggestions/${id}/apply`, {
        method: 'POST',
        body: JSON.stringify({ rows }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      qc.invalidateQueries({ queryKey: ['activity'] })
    },
  })
}

export const useSuggestShelfLife = () =>
  useMutation({
    mutationFn: (v: { name: string; description?: string }) =>
      api<ShelfLifeSuggestion>('/assistant/shelf-life', { method: 'POST', body: JSON.stringify(v) }),
  })
