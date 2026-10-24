import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getHealth } from '../api/client'
import RoleSwitcher from '../features/auth/RoleSwitcher'
import HelpChat from '../features/help/HelpChat'
import { useMe } from '../features/auth/api'
import type { ReactNode } from 'react'

export const NAV = [
  { path: '/dashboard', label: 'Dashboard', group: 'Overview', icon: 'grid' },
  { path: '/plan', label: 'Plan purchases', group: 'Operations', icon: 'cart' },
  { path: '/inventory', label: 'Inventory', group: 'Operations', icon: 'box' },
  { path: '/orders', label: 'Order history', group: 'Operations', icon: 'list' },
  { path: '/calendar', label: 'Calendar', group: 'Admin & Intelligence', icon: 'calendar', restricted: 'manager' },
  { path: '/activity', label: 'Activity', group: 'Admin & Intelligence', icon: 'pulse', restricted: 'manager' },
  { path: '/settings', label: 'Settings', group: 'Admin & Intelligence', icon: 'settings', restricted: 'owner' },
]

function NavIcon({ name }: { name: string }) {
  const paths: Record<string, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    cart: <><path d="M3 4h2l2.2 11h11.5l2-8H6"/><circle cx="9" cy="19" r="1"/><circle cx="18" cy="19" r="1"/></>,
    box: <><path d="m12 3 9 5v8l-9 5-9-5V8l9-5Z"/><path d="m3 8 9 5 9-5M12 13v8"/></>,
    list: <><path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6h.01M4 12h.01M4 18h.01"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
    pulse: <><path d="M3 12h4l3-8 4 16 3-8h4"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.6a8 8 0 0 1-1.8 1l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.8-1l-1.7.6-1.4-2.4 1.4-1.1a8 8 0 0 1 0-2l-1.4-1.1 1.4-2.4 1.7.6a8 8 0 0 1 1.8-1l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.8 1l1.7-.6 1.4 2.4-1.4 1.1a8 8 0 0 1-.1 1.9Z"/></>,
  }
  return <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function LockIcon() {
  return <svg aria-hidden="true" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>
}

export default function AppShell() {
  const [open, setOpen] = useState(false)
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false })
  const me = useMe()

  const sidebar = (
    <nav className="flex flex-col gap-5 p-3">
      {['Overview', 'Operations', 'Admin & Intelligence'].map((group) => <div key={group}>
        <div className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[.16em] text-slate-400">{group}</div>
        <div className="flex flex-col gap-1">{NAV.filter((n) => n.group === group).map((n) => (
        <NavLink
          key={n.path}
          to={n.path}
          onClick={() => setOpen(false)}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
              isActive ? 'bg-emerald-700 text-white shadow-sm' : 'text-slate-700 hover:bg-emerald-50 hover:text-emerald-900'
            }`
          }
        >
          <NavIcon name={n.icon} />
          <span className="flex-1">{n.label}</span>
          {me.data?.role === 'staff' && n.restricted && <span title={`Requires ${n.restricted} access`} className="opacity-60"><LockIcon /></span>}
        </NavLink>
      ))}</div></div>)}
    </nav>
  )

  return (
    <div className="flex min-h-[100dvh]">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-emerald-100 bg-[#fbfcf8] md:block">
        <div className="px-5 py-5 text-lg font-extrabold tracking-tight text-emerald-800">Restock<span className="text-slate-700">AI</span><span className="mt-0.5 block text-[10px] font-medium uppercase tracking-[.18em] text-slate-400">Kitchen purchasing</span></div>
        {sidebar}
      </aside>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-30 md:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/40" />
          <aside className="absolute left-0 top-0 h-full w-60 bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-5 text-lg font-extrabold text-emerald-800">RestockAI</div>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
          <button className="rounded-md p-2 text-slate-700 md:hidden" aria-label="Open menu" onClick={() => setOpen(true)}>
            <svg aria-hidden="true" width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
          </button>
          <span className="hidden text-sm text-slate-500 md:block">Smart purchase planning for your kitchen</span>
          <div className="flex items-center gap-3">
            <RoleSwitcher />
            <span className="text-xs text-slate-500" title="Backend connection">
              {health.isLoading ? 'Checking' : health.data?.status === 'ok' ? 'Online' : 'Offline'}
            </span>
          </div>
        </header>
        <main className="page-enter flex-1 p-4 md:p-7">
          <Outlet />
        </main>
      </div>
      <HelpChat />
    </div>
  )
}
