import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell, { NAV } from './layout/AppShell'
import Placeholder from './features/Placeholder'
import ActivityPage from './features/activity/ActivityPage'
import InventoryPage from './features/inventory/InventoryPage'

// Pages built so far; every other sidebar item shows a placeholder.
const PAGES: Record<string, React.ReactNode> = {
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
