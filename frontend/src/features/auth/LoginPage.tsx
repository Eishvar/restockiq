import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { setStoredUserId } from '../../api/client'
import { EmptyState } from '../../components/ui'
import { useUsers, type Role } from './api'

const ROLE: Record<Role, { label: string; can: string }> = {
  owner: { label: 'Owner', can: 'Sets up the business, approves and sends orders, changes settings.' },
  manager: { label: 'Manager', can: 'Plans purchases, edits and submits them, imports sales, updates stock.' },
  staff: { label: 'Staff', can: 'Views stock and updates quantities. Cannot plan or approve.' },
}

/** Demo login: pick who you want to be. A real deployment would put a password / SSO check here. */
export default function LoginPage() {
  const users = useUsers()
  const qc = useQueryClient()
  const navigate = useNavigate()

  function signIn(id: number) {
    setStoredUserId(String(id))
    qc.invalidateQueries()
    navigate('/', { replace: true })
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="text-2xl font-bold text-brand-royal">RestockAI</div>
          <p className="mt-1 text-sm text-slate-600">Smart purchase planning for your kitchen</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h1 className="text-lg font-semibold">Sign in</h1>
          <p className="mt-1 text-sm text-slate-600">
            This is a demo with made-up people. Choose who you want to be; there is no password.
          </p>
          <div className="mt-4 space-y-2">
            {users.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
            {users.error && <EmptyState title="Could not reach the server" hint={users.error.message} />}
            {users.data?.map((u) => (
              <button
                key={u.id}
                onClick={() => signIn(u.id)}
                className="w-full rounded-lg border border-slate-200 p-3 text-left transition hover:border-brand-royal hover:bg-brand-surface"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{u.name}</span>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{ROLE[u.role].label}</span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{ROLE[u.role].can}</p>
              </button>
            ))}
          </div>
          <p className="mt-4 text-xs text-slate-500">
            First time here? Sign in as the Owner to set up the business. Everyone in the demo uses made-up data.
          </p>
        </div>
      </div>
    </div>
  )
}
