import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

export type TripDetail = {
  date: string
  packs: number
  buy_base: number
  window_start: string
  window_end: string
  window_days: number
  window_need_base: number
  buffer_pct: number
  buffer_base: number
  target_base: number
  usable_base: number
  service_level: number | null
  n_samples: number
  method: string
}

export type Explanation = {
  daily_need: { date: string; need_base: number }[]
  stock: { qty_base: number; expires_on: string | null; expired: boolean; expired_base: number; purchase_date_unknown: boolean }
  trips: TripDetail[]
  service_level: number | null
  n_samples: number
  method: string
  shelf_life_days: number
  leftover_base: number
}

export type Line = {
  id: number
  ingredient_id: number
  name: string
  base_uom: string
  pack_uom: string
  pack_size_base: number
  need_base: number
  display_need: string
  buffer_pct: number
  buffer_base: number
  usable_stock_base: number
  display_usable_stock: string
  buy_schedule: { date: string; packs: number }[]
  suggested_packs: number
  final_packs: number
  display_buy: string
  pack_price_rm: number
  line_total_rm: number
  leftover_base: number
  explanation: Explanation
}

export type OrderStatus = 'draft' | 'pending_approval' | 'approved' | 'sent' | 'received' | 'rejected'

export type Order = {
  id: number
  run_id: number
  plan_today: string
  supplier_id: number
  supplier_name: string
  supplier_whatsapp: string
  min_order_rm: number
  status: OrderStatus
  total_rm: number
  warnings: string[]
  reject_reason: string | null
  created_at: string | null
  submitted_at: string | null
  approved_by: number | null
  approved_by_name: string | null
  approved_at: string | null
  sent_at: string | null
  received_at: string | null
  lines: Line[]
}

export type Drivers = {
  state: string
  weekday: string
  weekday_factor: number
  level: number
  strength: number
  holiday_effect: number
  event_effect: number
  names: string[]
  cold_start: boolean
}

export type Plan = {
  id: number
  created_at: string
  created_by_name: string | null
  today: string
  horizon_days: number
  risk_profile: string
  duration_ms: number
  calc_count: number
  manual_planning_hours: number
  grand_total_rm: number
  forecast: {
    days: { date: string; weekday: string; is_today: boolean; total: number; drivers: Drivers }[]
    dishes: { menu_item_id: number; name: string; category: string | null; qty: number[]; total: number }[]
    history: { date: string; total: number }[]
  }
  orders: Order[]
  discard: { ingredient_id: number; name: string; base_uom: string; qty_base: number; expired_on: string; days_ago: number }[]
  covered: { ingredient_id: number; name: string; base_uom: string; need_base: number; stock_base: number; expired: boolean }[]
  exceptions: Record<string, unknown>[]
  forecast_quality: {
    horizon_days: number
    wape_total: number
    baseline_naive_wape: number | null
    baseline_flat_wape: number | null
  } | null
}

export type SendResult = { order: Order; whatsapp_text: string; whatsapp_url: string | null; call_url: string | null }

export const usePlanContext = () =>
  useQuery({ queryKey: ['planning-context'], queryFn: () => api<{ today: string; last_plan_id: number | null }>('/planning/context') })

export const usePlan = (id: number | null) =>
  useQuery({ queryKey: ['plan', id], queryFn: () => api<Plan>(`/planning/plans/${id}`), enabled: id !== null })

export const useOrders = (status: string) =>
  useQuery({
    queryKey: ['orders', status],
    queryFn: () => api<Order[]>(`/planning/orders${status ? `?status=${status}` : ''}`),
  })

/** Writes refresh the plan, the dashboard, the activity log and (for receiving) the inventory. */
function useWrite<TVars, TOut>(fn: (v: TVars) => Promise<TOut>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      for (const key of ['plan', 'orders', 'planning-context', 'dashboard', 'activity', 'inventory'])
        qc.invalidateQueries({ queryKey: [key] })
    },
  })
}

export const useGeneratePlan = () =>
  useWrite((horizon_days: number) =>
    api<Plan>('/planning/plans', { method: 'POST', body: JSON.stringify({ horizon_days }) }),
  )

export const useEditLine = () =>
  useWrite(({ orderId, lineId, finalPacks }: { orderId: number; lineId: number; finalPacks: number }) =>
    api<Order>(`/planning/orders/${orderId}/lines/${lineId}`, {
      method: 'PATCH',
      body: JSON.stringify({ final_packs: finalPacks }),
    }),
  )

export type OrderAction = 'submit' | 'approve' | 'reject' | 'send' | 'receive'

export const useOrderAction = () =>
  useWrite(({ orderId, action, reason }: { orderId: number; action: OrderAction; reason?: string }) =>
    api<Order | SendResult>(`/planning/orders/${orderId}/${action}`, {
      method: 'POST',
      body: action === 'reject' ? JSON.stringify({ reason }) : undefined,
    }),
  )

/** Previews the supplier message without moving the order out of Draft. */
export const usePrepareOrderMessage = () =>
  useMutation({
    mutationFn: (orderId: number) => api<SendResult>(`/planning/orders/${orderId}/message`),
  })
