import { ApiError } from '../api'

export function RequestError({ error }: { error: Error | null }) {
  if (!error) return null
  if (error instanceof ApiError && error.status === 501) return <p role="status">Coming soon</p>
  if (error instanceof ApiError && error.status === 503) {
    if (error.code === 'brain_not_configured') return <p role="alert">Insights are unavailable until the Brain runtime is configured on the server.</p>
    if (error.code === 'llm_not_configured') return <p role="alert">AI suggestions are unavailable until the model provider is configured on the server.</p>
  }
  return <p role="alert">{error.message}</p>
}

export function QueryFeedback({ isPending, error }: { isPending: boolean; error: Error | null }) {
  if (isPending) return <p role="status">Loading…</p>
  return <RequestError error={error} />
}
