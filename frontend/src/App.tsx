import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell, { NAV } from './layout/AppShell'
import Placeholder from './features/Placeholder'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/plan" replace />} />
        {NAV.map((n) => (
          <Route key={n.path} path={n.path} element={<Placeholder title={n.label} />} />
        ))}
      </Route>
    </Routes>
  )
}
