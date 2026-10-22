import { EmptyState, Modal, Table } from '../../components/ui'
import { useMovements } from './api'

const REASON: Record<string, string> = {
  onboarding: 'Opening stock',
  adjust: 'Quantity changed',
  received: 'Delivery received',
  discard_expired: 'Expired, thrown away',
  removed: 'Item removed',
}

export default function HistoryModal({ ingredientId, name, onClose }: { ingredientId: number | null; name: string; onClose: () => void }) {
  const { data, isLoading, error } = useMovements(ingredientId)
  return (
    <Modal open={ingredientId !== null} title={`History: ${name}`} onClose={onClose}>
      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {error && <EmptyState title="Could not load the history" hint={error.message} />}
      {data && !data.length && <EmptyState title="No changes recorded yet" />}
      {data && data.length > 0 && (
        <Table head={['Date', 'Change', 'Why', 'Who']}>
          {data.map((m) => (
            <tr key={m.id}>
              <td className="whitespace-nowrap">{m.date}</td>
              <td className={`whitespace-nowrap font-medium ${m.change_base < 0 ? 'text-red-700' : 'text-emerald-700'}`}>{m.display_change}</td>
              <td>{REASON[m.reason] ?? m.reason}</td>
              <td>{m.user_name ?? '—'}</td>
            </tr>
          ))}
        </Table>
      )}
    </Modal>
  )
}
