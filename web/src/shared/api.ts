import { useQuery } from '@tanstack/react-query'
import { webEnv } from './env'

export const apiUrl = `${webEnv.apiBase}/v1`
export const appApiUrl = `${apiUrl}/apps/${encodeURIComponent(webEnv.appId)}`

export class ApiError extends Error {
  constructor(readonly status: number, message = `Request failed with HTTP ${status}`, readonly code?: string) {
    super(message)
  }
}

export async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body !== undefined) headers.set('Content-Type', 'application/json')
  const response = await fetch(url, { ...options, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const error = body?.error
    throw new ApiError(response.status, typeof error?.message === 'string' ? error.message : undefined, error?.code)
  }
  return response.json()
}

export function appWrite<T>(path: string, method: 'POST' | 'PUT', body?: unknown) {
  return request<T>(`${appApiUrl}${path}`, { method, body: JSON.stringify(body) })
}

export function useAppQuery<T>(queryKey: readonly string[], path: string) {
  return useQuery({
    queryKey,
    queryFn: ({ signal }) => request<T>(`${appApiUrl}${path}`, { signal }),
    retry: (failures, error) => {
      if (error instanceof ApiError && (error.status < 500 || error.status === 501
        || error.code === 'brain_not_configured' || error.code === 'llm_not_configured')) return false
      return failures < 2
    },
  })
}
