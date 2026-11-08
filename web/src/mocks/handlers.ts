import { http, HttpResponse } from 'msw'
import { appApiUrl } from '../shared/api'

export const handlers = [
  http.get(`${appApiUrl}/insights/latest`, () => HttpResponse.json({
    run_id: 'mock-run',
    source: 'offline',
    created_at: '2026-11-07T18:00:00Z',
    rankings: [],
    segments: [],
    uplift: [],
    tiers: [],
    hypotheses: [],
    flow_name: null,
  })),
  http.get(`${appApiUrl}/proposals`, () => HttpResponse.json([])),
  http.get(`${appApiUrl}/decisions`, () => HttpResponse.json([])),
]
