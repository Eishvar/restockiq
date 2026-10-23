import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getStoredUserId, setStoredUserId } from '../../api/client'
import { useMe, useUsers } from './api'

const ROLE_LABEL = { owner: 'Owner', manager: 'Manager', staff: 'Staff' }

/** Switch to another demo user without signing out (handy to show what each role may do), or sign out. */
export default function RoleSwitcher() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const users = useUsers()
  const stored = getStoredUserId()
  const valid = users.data?.some((u) => String(u.id) === stored)
  const me = useMe(!!valid)

  function choose(id: string) {
    setStoredUserId(id)
    qc.invalidateQueries() // refetch everything as the new user
  }

  function signOut() {
    try {
      localStorage.removeItem('restockiq_user_id')
    } catch {
      /* storage blocked: the login screen still works */
    }
    qc.clear()
    navigate('/login', { replace: true })
  }

  if (!users.data) return <span className="text-xs text-slate-500">…</span>

  return (
    <div className="flex items-center gap-2 text-sm">
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
      <button type="button" onClick={signOut} className="text-xs text-slate-500 underline hover:text-slate-800">
        Sign out
      </button>
    </div>
  )
}
