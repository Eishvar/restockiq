import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

export type Faq = { id: string; topic: string; question: string; answer: string }
export type HelpAnswer = { answer: string; source: 'faq' | 'cache' | 'ai' }

// The ready-made answers never change while the app is open, so they are fetched once and never again.
export const useFaq = (enabled: boolean) =>
  useQuery({ queryKey: ['help-faq'], queryFn: () => api<Faq[]>('/help/faq'), enabled, staleTime: Infinity, retry: false })

export const useHelpStatus = (enabled: boolean) =>
  useQuery({ queryKey: ['help-status'], queryFn: () => api<{ ai_available: boolean }>('/help/status'), enabled, staleTime: 60_000, retry: false })

export const useAskHelp = () =>
  useMutation({
    mutationFn: (v: { question: string; page: string }) =>
      api<HelpAnswer>('/help/ask', { method: 'POST', body: JSON.stringify(v) }),
  })
