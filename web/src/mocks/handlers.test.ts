import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'
import { apiUrl, appApiUrl, appWrite, request } from '../shared/api'
import type { FeatureProfile, MetricRule, RuleSuggestions } from '../types/ingest'
import type { AppSettings, Decision, InsightRun, LookupResult, Proposal } from '../types/targeting'
import { blockedExport, freeUser, mockProposal, paidUser } from './fixtures'
import { createHandlers } from './handlers'

const server = setupServer(...createHandlers())
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers(...createHandlers()))
afterAll(() => server.close())

describe('contract preview', () => {
  it('tracks each event once and returns the updated user profile', async () => {
    const events = [{ key: blockedExport, customer_user_id: freeUser, event_id: 'preview-event', occurred_at: new Date().toISOString(), props: {} }]
    expect(await appWrite('/events', 'POST', { events })).toEqual({ accepted: 1, duplicates: 0, unknown_keys: [] })
    expect(await appWrite('/events', 'POST', { events })).toEqual({ accepted: 0, duplicates: 1, unknown_keys: [] })
    const profile = await request<FeatureProfile>(`${appApiUrl}/users/${freeUser}/features`)
    expect(profile.features.find(({ feature }) => feature === 'hd_export')?.values.hd_export_uses_7d).toBe(1)
  })

  it('accepts a rule and keeps the new signal separate from historical uplift', async () => {
    const { suggestions } = await appWrite<RuleSuggestions>('/rules:suggest', 'POST')
    const saved = await appWrite<MetricRule>('/rules', 'POST', suggestions[0].rule)
    const result = await appWrite<InsightRun>('/insights:run', 'POST', { source: 'live' })
    expect(result.source).toBe('offline')
    expect(result.hypotheses).toEqual([saved.key])
    expect(result.uplift[0].test).toContain('lifetime anchor')
  })

  it('stores an approval, records its actor, and serves different preview flows', async () => {
    const edited = await request<Proposal>(`${apiUrl}/proposals/${mockProposal.proposal_id}`, {
      method: 'PATCH', body: JSON.stringify({ holdout_pct: 25 }),
    })
    expect(edited.edits[0]).toMatchObject({ field: 'holdout_pct', to: 25 })
    const approved = await request<Proposal>(`${apiUrl}/proposals/${mockProposal.proposal_id}:approve`, { method: 'POST' })
    expect(approved.status).toBe('live')
    expect(await request<Decision[]>(`${appApiUrl}/decisions`)).toEqual([expect.objectContaining({ decided_by: 'human' })])
    const lookup = await appWrite<{ results: LookupResult[] }>('/lookup', 'POST', {
      placement: 'main', customer_user_ids: [freeUser, paidUser],
    })
    expect(new Set(lookup.results.map((item) => item.flow_id)).size).toBe(2)
  })

  it('persists mode settings and records an eligible autopilot decision', async () => {
    const settings = await request<AppSettings>(`${appApiUrl}/settings`)
    await appWrite('/settings', 'PUT', { ...settings, mode: 'autopilot' })
    await appWrite('/insights:run', 'POST', { source: 'offline' })
    const [decision] = await request<Decision[]>(`${appApiUrl}/decisions`)
    expect(decision).toMatchObject({ action: 'autopilot_start', decided_by: 'autopilot' })
  })
})
