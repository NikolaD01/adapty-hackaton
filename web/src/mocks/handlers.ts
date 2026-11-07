import { http, HttpResponse } from 'msw'
import { webEnv } from '../shared/env'
import { eventTypes } from './eventTypes'

export const handlers = [
  http.get(`${webEnv.apiBase}/v1/apps/${webEnv.appId}/event-types`, () => {
    return HttpResponse.json(eventTypes)
  }),
]
