import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell, { NAV } from './layout/AppShell'
import Placeholder from './features/Placeholder'
import ActivityPage from './features/activity/ActivityPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/plan" replace />} />
        {NAV.map((n) => (
          <Route
            key={n.path}
            path={n.path}
            element={n.path === '/activity' ? <ActivityPage /> : <Placeholder title={n.label} />}
          />
        ))}
      </Route>
    </Routes>
  )
}
