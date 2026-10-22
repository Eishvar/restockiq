import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

export type RiskProfile = 'lean' | 'balanced' | 'never_run_out'

export type SupplierSettings = {
  id: number
  name: string
  category: string
  whatsapp: string
  min_order_rm: number
  delivery_days: string
  lead_time_days: number
}

export type Settings = {
  tenant_name: string
  risk_profile: RiskProfile
  manual_planning_hours: number
  today_override: string | null
  today: string
  service_levels: Record<RiskProfile, [number, number, number]>
  suppliers: SupplierSettings[]
  buffers_updated_at: string | null
}

export const useSettings = (enabled: boolean) =>
  useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings'), enabled, retry: false })

/** Settings change what plans, the dashboard and the forecast show, so refresh them all. */
function useRefresh() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries()
}

export const useSaveSettings = () => {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (patch: { risk_profile?: RiskProfile; manual_planning_hours?: number; today_override?: string | null }) =>
      api<Settings>('/settings', { method: 'PATCH', body: JSON.stringify(patch) }),
    onSuccess: refresh,
  })
}

export const useSaveSupplier = () => {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: ({ id, ...patch }: { id: number; whatsapp?: string; min_order_rm?: number }) =>
      api<SupplierSettings>(`/settings/suppliers/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
    onSuccess: refresh,
  })
}

export const useResetDemo = () => {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: () => api<{ status: string }>('/admin/reset', { method: 'POST' }),
    onSuccess: refresh,
  })
}
