import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError, getStoredUserId } from '../../api/client'

export type DraftRow = {
  i: number
  line: number
  date: string | null
  date_text: string
  dish: string
  item_id: number | null
  qty: number | null
  net: number | null
  problem: string | null
}

export type ImportPreview = {
  draft_id: number
  filename: string
  kind: 'csv' | 'xlsx' | 'pdf'
  read_by_ai: boolean
  notes: string | null
  rows_total: number
  rows_ok: number
  problems: number
  days: number
  date_from: string | null
  date_to: string | null
  new_days: number
  replaced_days: number
  dishes_sold: number
  net_sales_rm: number
  unmatched: { dish: string; rows: number }[]
  rows: DraftRow[]
  rows_shown: number
}

export type RowEdit = { i: number; drop?: boolean; date?: string; item_id?: number; qty?: number; net?: number }

export type ConfirmBody = { draft_id: number; edits: RowEdit[]; dish_map: Record<string, number | null> }

export type ImportResult = {
  import_id: number
  filename: string
  days: number
  rows_saved: number
  rows_left_out: number
  new_days: number
  replaced_days: number
  dishes_sold: number
  net_sales_rm: number
  date_from: string
  date_to: string
  today: string
}

export type ImportRecord = {
  id: number
  ts: string
  filename: string
  kind: 'csv' | 'xlsx' | 'pdf'
  read_by_ai: boolean
  date_from: string
  date_to: string
  days: number
  rows: number
  status: 'active' | 'removed'
  user_name: string | null
}

export type RemovedRecord = {
  id: number
  ts: string
  label: string
  date_from: string
  date_to: string
  days: number
  rows: number
  user_name: string | null
}

export type SalesOverview = {
  coverage: { first_date: string | null; last_date: string | null; days: number; rows: number }
  today: string
  today_is_demo_date: boolean
  imports: ImportRecord[]
  removed: RemovedRecord[]
  ai_available: boolean
}

export type RemoveTarget = { import_id?: number; date_from?: string; date_to?: string }

export type RemovePreview = {
  label: string
  date_from: string
  date_to: string
  days: number
  rows: number
  today_now: string
  today_after: string | null
}

export const useSalesOverview = () => useQuery({ queryKey: ['sales', 'overview'], queryFn: () => api<SalesOverview>('/sales/overview') })

export const useRemovePreview = (target: RemoveTarget | null) =>
  useQuery({
    queryKey: ['sales', 'remove-preview', target],
    queryFn: () => {
      const q = new URLSearchParams()
      for (const [k, v] of Object.entries(target ?? {})) if (v !== undefined) q.set(k, String(v))
      return api<RemovePreview>(`/sales/remove/preview?${q.toString()}`)
    },
    enabled: target !== null,
    retry: false,
  })

/** The file goes up as a form, not as JSON, so this does not use the shared helper. */
async function uploadForPreview(file: File): Promise<ImportPreview> {
  const form = new FormData()
  form.append('file', file)
  const userId = getStoredUserId()
  const res = await fetch('/api/sales/import/preview', { method: 'POST', body: form, headers: userId ? { 'X-User-Id': userId } : {} })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* body was not JSON */
    }
    throw new ApiError(res.status, String(detail))
  }
  return res.json() as Promise<ImportPreview>
}

export const usePreviewFile = () => useMutation({ mutationFn: uploadForPreview })

/** Sales change "today", plans, stock status and the accuracy badge, so everything is read again. */
function useSalesWrite<TVars, TOut>(fn: (v: TVars) => Promise<TOut>) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries() })
}

const send = (method: string, body?: unknown) => ({ method, body: body === undefined ? undefined : JSON.stringify(body) })

export const useConfirmImport = () => useSalesWrite((body: ConfirmBody) => api<ImportResult>('/sales/import/confirm', send('POST', body)))

export const useRemoveSales = () =>
  useSalesWrite((target: RemoveTarget) => api<{ removal: RemovedRecord; today: string }>('/sales/remove', send('POST', target)))

export const useRestoreSales = () =>
  useSalesWrite((id: number) => api<{ removal: RemovedRecord; today: string }>(`/sales/removals/${id}/restore`, send('POST')))

export const useDeleteForever = () => useSalesWrite((id: number) => api<RemovedRecord>(`/sales/removals/${id}`, send('DELETE')))

export async function downloadTemplate() {
  const userId = getStoredUserId()
  const res = await fetch('/api/sales/template.csv', { headers: userId ? { 'X-User-Id': userId } : {} })
  if (!res.ok) throw new ApiError(res.status, res.statusText)
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = 'sales_template.csv'
  a.click()
  URL.revokeObjectURL(url)
}
