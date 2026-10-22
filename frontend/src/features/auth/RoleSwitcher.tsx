import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getStoredUserId, setStoredUserId } from '../../api/client'
import { useMe, useUsers } from './api'

const ROLE_LABEL = { owner: 'Owner', manager: 'Manager', staff: 'Staff' }

/** Demo login: pick who you are. Every request then carries that user's id. */
export default function RoleSwitcher() {
  const qc = useQueryClient()
  const users = useUsers()
  const stored = getStoredUserId()
  const valid = users.data?.some((u) => String(u.id) === stored)
  const me = useMe(!!valid)

  // First visit (or stale id): sign in as the owner so the demo starts with full access.
  useEffect(() => {
    if (users.data && !valid) {
      const first = users.data.find((u) => u.role === 'owner') ?? users.data[0]
      if (first) {
        setStoredUserId(String(first.id))
        qc.invalidateQueries()
      }
    }
  }, [users.data, valid, qc])

  function choose(id: string) {
    setStoredUserId(id)
    qc.invalidateQueries() // refetch everything as the new user
  }

  if (!users.data) return <span className="text-xs text-slate-500">…</span>

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="hidden text-slate-500 sm:inline">Signed in as</span>
      <select
        aria-label="Switch user"
        value={valid ? stored! : ''}
        onChange={(e) => choose(e.target.value)}
        className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm"
      >
        {users.data.map((u) => (
          <option key={u.id} value={u.id}>
            {u.name} ({ROLE_LABEL[u.role]})
          </option>
        ))}
      </select>
      {me.data && <span className="hidden text-xs text-slate-500 lg:inline">{me.data.tenant_name}</span>}
    </label>
  )
}
