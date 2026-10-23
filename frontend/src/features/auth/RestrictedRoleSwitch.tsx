import { useQueryClient } from '@tanstack/react-query'
import { setStoredUserId } from '../../api/client'
import { Button } from '../../components/ui'
import { useMe, useUsers } from './api'

/** One-tap demo switch to the first real user allowed to view the restricted page. */
export default function RestrictedRoleSwitch({ permission }: { permission: 'manager' | 'owner' }) {
  const users = useUsers()
  const me = useMe()
  const client = useQueryClient()
  const target = users.data?.find((u) => permission === 'owner' ? u.role === 'owner' : u.role === 'owner' || u.role === 'manager')
  if (!target || target.id === me.data?.id) return null
  const targetId = target.id
  const role = target.role === 'owner' ? 'Owner' : 'Manager'
  async function switchUser() {
    await client.cancelQueries()
    setStoredUserId(String(targetId))
    await client.invalidateQueries()
  }
  return <Button variant="secondary" onClick={switchUser}>Switch to {target.name} ({role})</Button>
}
