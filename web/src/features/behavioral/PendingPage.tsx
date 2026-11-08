import { useAppQuery } from '../../shared/api'
import { QueryFeedback } from '../../shared/ui/QueryFeedback'
import { PlaceholderPage } from './PlaceholderPage'

export function PendingPage({ title, description, endpoint }: {
  title: string
  description: string
  endpoint?: string
}) {
  return (
    <>
      <PlaceholderPage title={title} description={description} />
      {endpoint ? <PendingResource endpoint={endpoint} /> : <p role="status">Coming soon</p>}
    </>
  )
}

function PendingResource({ endpoint }: { endpoint: string }) {
  const query = useAppQuery(['pending', endpoint], endpoint)
  return query.isSuccess ? <p role="status">Coming soon</p> : <QueryFeedback {...query} />
}
