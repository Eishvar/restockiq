import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

export type ActivityRow = {
  id: number
  ts: string
  user_id: number | null
  user_name: string | null
  role: string | null
  action: string
  entity_type: string | null
  entity_id: string | null
  details: Record<string, unknown> | null
}

export const useActivity = () =>
  useQuery({ queryKey: ['activity'], queryFn: () => api<ActivityRow[]>('/activity?limit=100'), retry: false })
