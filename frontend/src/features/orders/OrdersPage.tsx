import SupplierOrdersBoard from '../planning/SupplierOrdersBoard'

/** The Plan page and Orders page share the same supplier-based three-lane workflow. */
export default function OrdersPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Orders</h1>
        <p className="text-sm text-slate-600">Supplier lists are grouped by status. Expand a supplier to review or update its orders.</p>
      </div>
      <SupplierOrdersBoard />
    </div>
  )
}
