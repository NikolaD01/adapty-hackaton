import { useQuery } from '@tanstack/react-query'
import { webEnv } from './env'

export const appApiUrl = `${webEnv.apiBase}/v1/apps/${encodeURIComponent(webEnv.appId)}`

export class ApiError extends Error {
  constructor(readonly status: number) {
    super(`Request failed with HTTP ${status}`)
  }
}

async function get<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(`${appApiUrl}${path}`, { signal })
  if (!response.ok) throw new ApiError(response.status)
  return response.json()
}

export function useAppQuery<T>(queryKey: readonly string[], path: string) {
  return useQuery({
    queryKey,
    queryFn: ({ signal }) => get<T>(path, signal),
    retry: (failures, error) => {
      if (error instanceof ApiError && (error.status < 500 || error.status === 501)) return false
      return failures < 2
    },
  })
}
