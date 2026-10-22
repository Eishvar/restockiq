import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell, { NAV } from './layout/AppShell'
import Placeholder from './features/Placeholder'

// Each page is its own download, so the first screen loads fast (the charts library alone is large).
const page = (load: () => Promise<{ default: React.ComponentType }>) => {
  const Page = lazy(load)
  return <Page />
}

// Pages built so far; every other sidebar item shows a placeholder.
const PAGES: Record<string, React.ReactNode> = {
  '/plan': page(() => import('./features/planning/PlanPage')),
  '/inventory': page(() => import('./features/inventory/InventoryPage')),
  '/orders': page(() => import('./features/orders/OrdersPage')),
  '/dashboard': page(() => import('./features/dashboard/DashboardPage')),
  '/calendar': page(() => import('./features/calendar/CalendarPage')),
  '/activity': page(() => import('./features/activity/ActivityPage')),
  '/settings': page(() => import('./features/settings/SettingsPage')),
}

export default function App() {
  return (
    <Suspense fallback={<p className="p-6 text-sm text-slate-500">Loading…</p>}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/plan" replace />} />
          {NAV.map((n) => (
            <Route key={n.path} path={n.path} element={PAGES[n.path] ?? <Placeholder title={n.label} />} />
          ))}
        </Route>
      </Routes>
    </Suspense>
  )
}
