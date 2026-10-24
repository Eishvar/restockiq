import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell, { NAV } from './layout/AppShell'
import Placeholder from './features/Placeholder'
import LoginPage from './features/auth/LoginPage'
import { RequireSetup, RequireUser } from './features/auth/Guards'
import { PageSkeleton } from './components/ui'

// Each page is its own download, so the first screen loads fast (the charts library alone is large).
const page = (load: () => Promise<{ default: React.ComponentType }>) => {
  const Page = lazy(load)
  return <Page />
}

const PAGES: Record<string, React.ReactNode> = {
  '/plan': page(() => import('./features/planning/PlanPage')),
  '/inventory': page(() => import('./features/inventory/InventoryPage')),
  '/recipes': page(() => import('./features/recipes/RecipesPage')),
  '/orders': page(() => import('./features/orders/OrdersPage')),
  '/dashboard': page(() => import('./features/dashboard/DashboardPage')),
  '/calendar': page(() => import('./features/calendar/CalendarPage')),
  '/activity': page(() => import('./features/activity/ActivityPage')),
  '/settings': page(() => import('./features/settings/SettingsPage')),
}

const SETUP = page(() => import('./features/setup/SetupWizard'))
const FEEDME = page(() => import('./features/pos/FeedMePage'))

export default function App() {
  return (
    <Suspense fallback={<div className="p-6"><PageSkeleton rows={3} /></div>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireUser />}>
          {/* Full-page screens: the first-time wizard and the stand-in for the FeedMe till */}
          <Route path="/setup" element={SETUP} />
          <Route path="/pos/feedme" element={FEEDME} />
          <Route element={<RequireSetup />}>
            <Route element={<AppShell />}>
              <Route index element={<Navigate to="/plan" replace />} />
              {NAV.map((n) => (
                <Route key={n.path} path={n.path} element={PAGES[n.path] ?? <Placeholder title={n.label} />} />
              ))}
            </Route>
          </Route>
        </Route>
      </Routes>
    </Suspense>
  )
}
