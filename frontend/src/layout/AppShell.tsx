import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getHealth } from '../api/client'
import RoleSwitcher from '../features/auth/RoleSwitcher'

export const NAV = [
  { path: '/plan', label: 'Plan purchases' },
  { path: '/inventory', label: 'Inventory' },
  { path: '/orders', label: 'Orders' },
  { path: '/dashboard', label: 'Dashboard' },
  { path: '/calendar', label: 'Calendar' },
  { path: '/recipes', label: 'Recipes' },
  { path: '/activity', label: 'Activity' },
  { path: '/settings', label: 'Settings' },
]

export default function AppShell() {
  const [open, setOpen] = useState(false)
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false })

  const sidebar = (
    <nav className="flex flex-col gap-1 p-3">
      {NAV.map((n) => (
        <NavLink
          key={n.path}
          to={n.path}
          onClick={() => setOpen(false)}
          className={({ isActive }) =>
            `rounded-lg px-3 py-2 text-sm font-medium ${
              isActive ? 'bg-emerald-600 text-white' : 'text-slate-700 hover:bg-slate-100'
            }`
          }
        >
          {n.label}
        </NavLink>
      ))}
    </nav>
  )

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside className="hidden w-56 shrink-0 border-r border-slate-200 bg-white md:block">
        <div className="px-4 py-4 text-lg font-bold text-emerald-700">RestockIQ</div>
        {sidebar}
      </aside>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-30 md:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/40" />
          <aside className="absolute left-0 top-0 h-full w-60 bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="px-4 py-4 text-lg font-bold text-emerald-700">RestockIQ</div>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
          <button className="rounded-md p-1 text-xl md:hidden" aria-label="Open menu" onClick={() => setOpen(true)}>
            ☰
          </button>
          <span className="hidden text-sm text-slate-500 md:block">Smart purchase planning for your kitchen</span>
          <div className="flex items-center gap-3">
            <RoleSwitcher />
            <span className="text-xs text-slate-500" title="Backend connection">
              {health.isLoading ? '…' : health.data?.status === 'ok' ? '● online' : '○ offline'}
            </span>
          </div>
        </header>
        <main className="flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
