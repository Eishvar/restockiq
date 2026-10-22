import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

export type Dashboard = {
  today: string
  plans_total: number
  plans_completed: number
  manual_hours_per_plan: number
  hours_saved: number
  avg_review_minutes: number | null
  last_plan: { id: number; created_at: string; today: string; horizon_days: number; duration_ms: number; grand_total_rm: number } | null
  accuracy: { horizon_days: number; wape_total: number; baseline_naive_wape: number | null; baseline_flat_wape: number | null } | null
  orders: { id: number; supplier_name: string; status: string; total_rm: number }[]
  inventory: {
    ok: number
    expiring_soon: number
    expired: number
    expired_items: string[]
    expiring_items: { name: string; days_left: number }[]
  }
  top_spend: { name: string; total_rm: number }[]
}

export const useDashboard = () => useQuery({ queryKey: ['dashboard'], queryFn: () => api<Dashboard>('/dashboard') })
