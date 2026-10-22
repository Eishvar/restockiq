import type { ButtonHTMLAttributes } from 'react'
import { Button, Tooltip } from '../../components/ui'
import { useMe } from '../auth/api'

type Need = 'owner' | 'manager'

/** Role of the signed-in person, with the two checks the screens need. */
export function useRole() {
  const role = useMe().data?.role
  return { role, isOwner: role === 'owner', isManager: role === 'owner' || role === 'manager' }
}

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  allowed: boolean
  need: Need
  verb: string // "approve this order"
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
}

/** A button that stays visible but is disabled, with a tooltip naming the role that can use it. */
export default function GatedButton({ allowed, need, verb, disabled, ...props }: Props) {
  const button = <Button {...props} disabled={!allowed || disabled} />
  if (allowed) return button
  const who = need === 'owner' ? 'the owner' : 'managers and the owner'
  return <Tooltip text={`Only ${who} can ${verb}`}>{button}</Tooltip>
}
