import { Card, EmptyState } from '../components/ui'

export default function Placeholder({ title }: { title: string }) {
  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <h1 className="text-xl font-semibold">{title}</h1>
      <Card>
        <EmptyState title="Coming soon" hint={`${title} will be built in a later module.`} />
      </Card>
    </div>
  )
}
