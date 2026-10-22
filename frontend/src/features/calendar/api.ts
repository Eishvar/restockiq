import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

export type EventType = 'period' | 'public_holiday' | 'local_event'

export type CalendarEvent = {
  id: number
  type: EventType
  label: string | null
  name: string
  start_date: string
  end_date: string
  status: string
  source: string
}

export type CalendarData = { today: string; events: CalendarEvent[]; labels: string[]; buffers_updated_at: string | null }
export type EventInput = { type: EventType; label: string | null; name: string; start_date: string; end_date: string }

export const useCalendar = (enabled: boolean) =>
  useQuery({ queryKey: ['calendar'], queryFn: () => api<CalendarData>('/calendar'), enabled, retry: false })

/** The calendar feeds the forecast, so the next plan and the activity record should refresh too. */
function useRefresh() {
  const qc = useQueryClient()
  return () => {
    for (const key of ['calendar', 'activity', 'settings']) qc.invalidateQueries({ queryKey: [key] })
  }
}

export const useAddEvent = () => {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (e: EventInput) => api<CalendarEvent>('/calendar', { method: 'POST', body: JSON.stringify(e) }),
    onSuccess: refresh,
  })
}

export const useEditEvent = () => {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: ({ id, ...e }: EventInput & { id: number }) =>
      api<CalendarEvent>(`/calendar/${id}`, { method: 'PATCH', body: JSON.stringify(e) }),
    onSuccess: refresh,
  })
}

export const useDeleteEvent = () => {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/calendar/${id}`, { method: 'DELETE' }),
    onSuccess: refresh,
  })
}

export const useRecompute = () => {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: () => api<{ origins: number; profiles: number; seconds: number }>('/calendar/recompute', { method: 'POST' }),
    onSuccess: refresh,
  })
}
