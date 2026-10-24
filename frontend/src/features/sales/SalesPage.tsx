import SalesPanel from './SalesPanel'

export default function SalesPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Sales data</h1>
        <p className="mt-1 text-sm text-slate-600">
          The forecast learns from your sales. Add the sales report from your till as a CSV, Excel or PDF file, check what was read, and save it.
          If something was wrong, remove it and add the right file. Nothing is lost until you delete it forever.
        </p>
      </div>
      <SalesPanel mode="page" />
    </div>
  )
}
