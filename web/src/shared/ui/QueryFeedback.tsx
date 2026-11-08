import { ApiError } from '../api'

export function QueryFeedback({ isPending, error }: { isPending: boolean; error: Error | null }) {
  if (isPending) return <p role="status">Loading…</p>
  if (error instanceof ApiError && error.status === 501) return <p role="status">Coming soon</p>
  if (error) return <p role="alert">Could not load data. {error.message}</p>
  return null
}
