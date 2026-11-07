import { QueryClient } from '@tanstack/react-query'
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest'
import { server } from '../mocks/server'
import { webEnv } from '../shared/env'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

it('serves the event catalog contract example through MSW', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  const catalog = await client.fetchQuery({
    queryKey: ['event-types', webEnv.appId],
    queryFn: async () => {
      const response = await fetch(`${webEnv.apiBase}/v1/apps/${webEnv.appId}/event-types`)
      expect(response.status).toBe(200)
      return response.json()
    },
  })

  expect(catalog).toEqual([
    {
      action_id: 3,
      key: 'bg_remove',
      name: 'Background removed',
      description: 'User removed the background of a photo with the AI tool',
      family: 'background',
      created_at: '2026-11-07T18:00:00Z',
    },
  ])
})
