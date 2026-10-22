// Thin fetch wrapper. All API calls go to /api (proxied to FastAPI in development).
// The simulated login is just a user id kept in localStorage and sent as X-User-Id.
const USER_KEY = 'restockiq_user_id'

export function getStoredUserId(): string | null {
  try {
    return localStorage.getItem(USER_KEY)
  } catch {
    return null
  }
}

export function setStoredUserId(id: string) {
  try {
    localStorage.setItem(USER_KEY, id)
  } catch {
    /* storage blocked: the switcher falls back to the owner on each load */
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const userId = getStoredUserId()
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(userId ? { 'X-User-Id': userId } : {}),
      ...init?.headers,
    },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* body was not JSON */
    }
    throw new ApiError(res.status, String(detail))
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const getHealth = () => api<{ status: string; app: string }>('/health')
