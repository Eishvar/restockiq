import { Button, useToast } from '../../components/ui'

/** The order note written when the owner approved, shown as saved so what was approved is what gets sent. */
export default function OrderNote({ text }: { text: string }) {
  const toast = useToast()

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      toast('Order note copied', 'success')
    } catch {
      toast('Could not copy. Select the text and copy it by hand.', 'error')
    }
  }

  return (
    <details className="mt-3 rounded-lg border border-slate-200 bg-white p-3 text-sm">
      <summary className="cursor-pointer font-medium text-brand-royal">Order note for the supplier</summary>
      <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3">{text}</pre>
      <div className="mt-2"><Button variant="secondary" onClick={copy}>Copy note</Button></div>
    </details>
  )
}
