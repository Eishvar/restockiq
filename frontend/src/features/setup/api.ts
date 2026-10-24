import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

export type SetupStep = 'country' | 'pos' | 'inventory' | 'recipes' | 'calendar' | 'done'

export type SetupStatus = {
  step: SetupStep
  complete: boolean
  country: string | null
  country_name: string | null
  currency: string | null
  pos_provider: string | null
  pos_connected_at: string | null
  inventory_done: boolean
  recipes_done: boolean
  calendar_skipped: boolean
}

export type CountryResult = { status: SetupStatus; holidays_added: number; holidays_already_there: number }

export const useSetupStatus = (enabled = true) =>
  useQuery({ queryKey: ['setup'], queryFn: () => api<SetupStatus>('/setup/status'), enabled, retry: false })

export const useChooseCountry = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (country: string) => api<CountryResult>('/setup/country', { method: 'POST', body: JSON.stringify({ country }) }),
    onSuccess: () => {
      for (const key of ['setup', 'calendar', 'activity']) qc.invalidateQueries({ queryKey: [key] })
    },
  })
}

export const useConfirmRecipes = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api<SetupStatus>('/setup/recipes/confirm', { method: 'POST' }),
    onSuccess: () => {
      for (const key of ['setup', 'activity']) qc.invalidateQueries({ queryKey: [key] })
    },
  })
}

export const useCompleteSetup = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (skipCalendar: boolean) =>
      api<SetupStatus>('/setup/complete', { method: 'POST', body: JSON.stringify({ skip_calendar: skipCalendar }) }),
    onSuccess: () => {
      for (const key of ['setup', 'activity']) qc.invalidateQueries({ queryKey: [key] })
    },
  })
}
