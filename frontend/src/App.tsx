import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell, { NAV } from './layout/AppShell'
import Placeholder from './features/Placeholder'
import ActivityPage from './features/activity/ActivityPage'
import InventoryPage from './features/inventory/InventoryPage'
import DashboardPage from './features/dashboard/DashboardPage'
import PlanPage from './features/planning/PlanPage'

// Pages built so far; every other sidebar item shows a placeholder.
const PAGES: Record<string, React.ReactNode> = {
  '/plan': <PlanPage />,
  '/dashboard': <DashboardPage />,
  '/inventory': <InventoryPage />,
  '/activity': <ActivityPage />,
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/plan" replace />} />
        {NAV.map((n) => (
          <Route
            key={n.path}
            path={n.path}
            element={PAGES[n.path] ?? <Placeholder title={n.label} />}
          />
        ))}
      </Route>
    </Routes>
  )
}
