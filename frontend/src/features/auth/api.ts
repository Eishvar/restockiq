import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

export type Role = 'owner' | 'manager' | 'staff'
export type User = { id: number; name: string; role: Role }
export type Me = User & { tenant_id: number; tenant_name: string }

export const useUsers = () => useQuery({ queryKey: ['users'], queryFn: () => api<User[]>('/users') })

export const useMe = (enabled = true) =>
  useQuery({ queryKey: ['me'], queryFn: () => api<Me>('/me'), enabled, retry: false })
