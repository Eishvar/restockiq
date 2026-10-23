import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, getStoredUserId } from '../../api/client'

export type PosStatus = {
  provider: string | null
  connected_at: string | null
  latest_sales_date: string | null
  today: string
  next_to_import: string | null
  last_import: {
    ts: string
    filename: string
    date_from: string
    date_to: string
    days: number
    rows: number
    user_name: string | null
  } | null
}

export type ImportSummary = {
  rows_total: number
  rows_ok: number
  days: number
  date_from: string | null
  date_to: string | null
  new_days: number
  replaced_days: number
  dishes_sold: number
  net_sales_rm: number
  unmatched: { name: string; rows: number }[]
  bad_count: number
  bad_rows: { line: number; reason: string }[]
}

export type FeedMeDay = { date: string; dishes: number; net_sales_rm: number; imported: boolean }
export type FeedMePreview = { columns: string[]; rows: string[][]; total_rows: number; date_from: string; date_to: string }

export const usePosStatus = (enabled = true) =>
  useQuery({ queryKey: ['pos'], queryFn: () => api<PosStatus>('/pos/status'), enabled, retry: false })

export const useConnectPos = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (provider: string) => api<PosStatus>('/pos/connect', { method: 'POST', body: JSON.stringify({ provider }) }),
    onSuccess: () => {
      for (const key of ['pos', 'setup', 'activity']) qc.invalidateQueries({ queryKey: [key] })
    },
  })
}

export const usePreviewImport = () =>
  useMutation({
    mutationFn: (csvText: string) =>
      api<ImportSummary>('/pos/import/preview', { method: 'POST', body: JSON.stringify({ filename: '', csv_text: csvText }) }),
  })

/** New sales move "today" and the forecast, so everything on screen is refreshed. */
export const useImportSales = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ filename, csvText }: { filename: string; csvText: string }) =>
      api<ImportSummary>('/pos/import', { method: 'POST', body: JSON.stringify({ filename, csv_text: csvText }) }),
    onSuccess: () => qc.invalidateQueries(),
  })
}

// ---- the simulated FeedMe screen ----
export const useFeedMeDays = () =>
  useQuery({ queryKey: ['feedme-days'], queryFn: () => api<FeedMeDay[]>('/pos/feedme/days'), retry: false })

export const useFeedMePreview = (from: string, to: string) =>
  useQuery({
    queryKey: ['feedme-preview', from, to],
    queryFn: () => api<FeedMePreview>(`/pos/feedme/preview?date_from=${from}&date_to=${to}`),
    enabled: !!from && !!to && to >= from,
    retry: false,
  })

/** Download the simulated export as a CSV file (a plain link cannot send the login header). */
export async function downloadFeedMeCsv(from: string, to: string): Promise<string> {
  const userId = getStoredUserId()
  const res = await fetch(`/api/pos/feedme/export.csv?date_from=${from}&date_to=${to}`, {
    headers: userId ? { 'X-User-Id': userId } : {},
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* not JSON */
    }
    throw new Error(String(detail))
  }
  const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? 'feedme_sales.csv'
  const url = URL.createObjectURL(await res.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
  return name
}
