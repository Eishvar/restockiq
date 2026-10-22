// Thin fetch wrapper. All API calls go to /api (proxied to FastAPI in development).
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const getHealth = () => api<{ status: string; app: string }>('/health')
