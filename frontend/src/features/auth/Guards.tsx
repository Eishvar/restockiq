import { Navigate, Outlet } from 'react-router-dom'
import { getStoredUserId } from '../../api/client'
import { useSetupStatus } from '../setup/api'
import { useMe, useUsers } from './api'

const Loading = () => <p className="p-6 text-sm text-slate-500">Loading…</p>

/** Everything except /login needs a signed-in (demo) user. */
export function RequireUser() {
  const users = useUsers()
  const stored = getStoredUserId()
  if (users.isLoading) return <Loading />
  const valid = users.data?.some((u) => String(u.id) === stored)
  return valid ? <Outlet /> : <Navigate to="/login" replace />
}

/** The owner is sent through the setup wizard until it is finished. Other roles are never blocked. */
export function RequireSetup() {
  const me = useMe()
  const isOwner = me.data?.role === 'owner'
  const setup = useSetupStatus(isOwner)
  if (me.isLoading || (isOwner && setup.isLoading)) return <Loading />
  if (isOwner && setup.data && !setup.data.complete) return <Navigate to="/setup" replace />
  return <Outlet />
}
