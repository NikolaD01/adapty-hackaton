import type { EventType, EventTypeInput, Feature, FeatureInput, QueuedEvent } from 'feature-signal-sdk'
import { http, HttpResponse } from 'msw'
import { apiUrl, appApiUrl } from '../shared/api'
import type { FeatureProfile, MetricRule, RuleInput, Timeline } from '../types/ingest'
import type { AppSettings, Decision, InsightRun, InsightSource, Proposal, ProposalPatch } from '../types/targeting'
import { freeUser, mockEvents, mockFeatures, mockInsight, mockProposal, mockSettings, mockSuggestions, paidUser } from './fixtures'

function error(status: number, code: string, message: string) {
  return HttpResponse.json({ error: { code, message, details: {} } }, { status })
}

export function createHandlers() {
  const features = new Map(mockFeatures.map((feature) => [feature.key, feature]))
  const eventTypes = new Map(mockEvents.map((event) => [event.key, event]))
  const history = new Map<string, Timeline['items'][number] & { customer_user_id: string }>()
  const rules = new Map<string, MetricRule>()
  const proposals = new Map<string, Proposal>([[mockProposal.proposal_id, structuredClone(mockProposal)]])
  const decisions: Decision[] = []
  let settings = structuredClone(mockSettings)
  let insight = structuredClone(mockInsight)
  let nextEventId = mockEvents.length + 1
  let nextRuleId = 1

  function saveRule(input: RuleInput) {
    const rule = {
      ...input,
      rule_id: rules.get(input.key)?.rule_id ?? nextRuleId++,
      created_at: rules.get(input.key)?.created_at ?? new Date().toISOString(),
    }
    rules.set(rule.key, rule)
    return rule
  }

  function syncDefaultRules(feature: Feature) {
    const keys = [...eventTypes.values()].filter((event) => event.features.includes(feature.key)).map((event) => event.key)
    const defaults: { suffix: string; definition: RuleInput['definition'] }[] = keys.length === 0 ? [] : [
      { suffix: 'uses_total', definition: { measure: 'count', event_keys: keys } },
      { suffix: 'uses_7d', definition: { measure: 'count', event_keys: keys, window_days: 7 } },
      { suffix: 'days_active_7d', definition: { measure: 'days_active', event_keys: keys, window_days: 7 } },
      ...keys.map((key) => ({
        suffix: `used_${key}`, definition: { measure: 'exists' as const, event_keys: [key] },
      })),
    ]
    for (const rule of rules.values()) {
      if (rule.feature === feature.key && rule.source === 'default' && !defaults.some(({ suffix }) => rule.key === `${feature.key}_${suffix}`)) {
        rules.delete(rule.key)
      }
    }
    for (const { suffix, definition } of defaults) {
      saveRule({
        key: `${feature.key}_${suffix}`, name: `${feature.name} · ${suffix.replaceAll('_', ' ')}`,
        description: 'Default feature metric.', source: 'default', feature: feature.key, value_type: 'float', definition,
      })
    }
  }

  function valueFor(userId: string, { definition }: RuleInput) {
    const cutoff = definition.window_days ? Date.now() - definition.window_days * 86_400_000 : -Infinity
    const matching = [...history.values()].filter((event) =>
      event.customer_user_id === userId && definition.event_keys.includes(event.key) && Date.parse(event.occurred_at) >= cutoff)
    if (definition.measure === 'days_active') return new Set(matching.map((event) => event.occurred_at.slice(0, 10))).size
    if (definition.measure === 'exists') return Number(matching.length > 0)
    return matching.length
  }

  for (const feature of features.values()) syncDefaultRules(feature)

  function decide(proposal: Proposal, status: 'live' | 'rejected' | 'awaiting_publish', action: Decision['action'], reason?: string) {
    const at = new Date().toISOString()
    const actor = action === 'autopilot_start' ? 'autopilot' : 'human'
    const updated: Proposal = { ...proposal, status, decided_by: actor, mode_at_decision: settings.mode, updated_at: at }
    if (status === 'live') {
      updated.adapty = { segment_id: 'preview-segment', placement_id: 'preview-placement', ab_test_id: 'preview-test', attributes_written: 1 }
    }
    proposals.set(updated.proposal_id, updated)
    const steps = status === 'rejected' ? ['rejected'] : status === 'awaiting_publish'
      ? ['write_attributes', 'segments_create', 'awaiting_publish']
      : ['write_attributes', 'segments_create', 'placement_read', 'ab_tests_create', 'ab_tests_start']
    decisions.unshift({
      decision_id: `dc_preview_${decisions.length + 1}`, proposal_id: updated.proposal_id,
      decided_by: actor, action, at, steps: steps.map((step) => ({ step, ok: true, detail: reason ? { reason } : {} })),
    })
    return updated
  }

  return [
    http.get(`${appApiUrl}/features`, () => HttpResponse.json([...features.values()])),
    http.post(`${appApiUrl}/features`, async ({ request }) => {
      const input = await request.json() as FeatureInput
      const feature = { ...input, plans: input.plans ?? [], created_at: features.get(input.key)?.created_at ?? new Date().toISOString() }
      features.set(feature.key, feature)
      syncDefaultRules(feature)
      return HttpResponse.json(feature)
    }),
    http.get(`${appApiUrl}/event-types`, () => HttpResponse.json([...eventTypes.values()])),
    http.post(`${appApiUrl}/event-types`, async ({ request }) => {
      const input = await request.json() as EventTypeInput
      const related = input.features ?? []
      if (related.some((key) => !features.has(key))) return error(422, 'unknown_feature', 'An event refers to an unknown feature.')
      const previous = eventTypes.get(input.key)
      const event: EventType = {
        ...input, features: related, action_id: previous?.action_id ?? nextEventId++,
        created_at: previous?.created_at ?? new Date().toISOString(),
      }
      eventTypes.set(event.key, event)
      for (const feature of features.values()) {
        if (related.includes(feature.key) || previous?.features.includes(feature.key)) syncDefaultRules(feature)
      }
      return HttpResponse.json(event)
    }),
    http.post(`${appApiUrl}/events`, async ({ request }) => {
      const { events } = await request.json() as { events: QueuedEvent[] }
      const unknown = new Set<string>()
      let accepted = 0
      let duplicates = 0
      for (const event of events) {
        if (!eventTypes.has(event.key)) unknown.add(event.key)
        else if (history.has(event.event_id)) duplicates++
        else {
          history.set(event.event_id, { ...event, received_at: new Date().toISOString() })
          accepted++
        }
      }
      return HttpResponse.json({ accepted, duplicates, unknown_keys: [...unknown] })
    }),
    http.get(`${appApiUrl}/users/:userId/timeline`, ({ params, request }) => {
      const limit = Number(new URL(request.url).searchParams.get('limit') ?? 50)
      const items = [...history.values()].filter((event) => event.customer_user_id === params.userId)
        .sort((a, b) => b.occurred_at.localeCompare(a.occurred_at)).slice(0, limit)
        .map(({ customer_user_id: _userId, ...event }) => event)
      return HttpResponse.json({ customer_user_id: params.userId, items })
    }),
    http.get(`${appApiUrl}/users/:userId/features`, ({ params }) => {
      const userId = String(params.userId)
      const profile: FeatureProfile = {
        customer_user_id: userId,
        features: [...features.values()].map((feature) => {
          const values = Object.fromEntries([...rules.values()].filter((rule) => rule.feature === feature.key)
            .map((rule) => [rule.key, valueFor(userId, rule)]))
          const uses = values.ai_enhance_uses_7d ?? 0
          return {
            feature: feature.key, name: feature.name, values,
            tier: feature.key === 'ai_enhance' ? uses <= 2 ? 'low' : uses <= 7 ? 'mid' : 'high' : null,
          }
        }),
      }
      return HttpResponse.json(profile)
    }),
    http.get(`${appApiUrl}/rules`, () => HttpResponse.json([...rules.values()])),
    http.post(`${appApiUrl}/rules`, async ({ request }) => HttpResponse.json(saveRule(await request.json() as RuleInput))),
    http.get(`${appApiUrl}/values`, ({ request }) => {
      const limit = Number(new URL(request.url).searchParams.get('limit') ?? 100)
      const items = [freeUser, paidUser].flatMap((customer_user_id) => [...rules.values()].map((rule) => ({
        customer_user_id, rule_key: rule.key, value: valueFor(customer_user_id, rule), computed_at: new Date().toISOString(),
      })))
      return HttpResponse.json({ items: items.slice(0, limit), next_cursor: items.length > limit ? String(limit) : null })
    }),
    http.post(`${appApiUrl}/rules:suggest`, () => HttpResponse.json(mockSuggestions)),
    http.get(`${appApiUrl}/insights/latest`, () => HttpResponse.json(insight)),
    http.post(`${appApiUrl}/insights:run`, async ({ request }) => {
      const { source } = await request.json() as { source: InsightSource }
      insight = {
        ...mockInsight, source: 'offline', created_at: new Date().toISOString(),
        hypotheses: [...rules.values()].filter((rule) => rule.source === 'ai').map((rule) => rule.key),
      }
      const draft = proposals.get(mockProposal.proposal_id)
      if (source && draft?.status === 'draft' && settings.mode === 'autopilot'
        && settings.autopilot.max_live_proposals > 0 && draft.holdout_pct >= settings.autopilot.min_holdout_pct) {
        decide(draft, draft.action.needs_publish ? 'awaiting_publish' : 'live', 'autopilot_start')
      }
      return HttpResponse.json(insight)
    }),
    http.get(`${appApiUrl}/proposals`, ({ request }) => {
      const status = new URL(request.url).searchParams.get('status')
      return HttpResponse.json([...proposals.values()].filter((proposal) => !status || status === proposal.status))
    }),
    http.patch(`${apiUrl}/proposals/:id`, async ({ params, request }) => {
      const proposal = proposals.get(String(params.id))
      if (!proposal) return error(404, 'proposal_not_found', 'Proposal not found.')
      if (proposal.status !== 'draft') return error(409, 'proposal_not_editable', 'Only a draft proposal can be edited.')
      const { flow_id, condition_value, ...fields } = await request.json() as ProposalPatch
      const at = new Date().toISOString()
      const changes = [
        ...Object.entries(fields).map(([field, to]) => ({ field, to, from: proposal[field as keyof Proposal], at })),
        ...(flow_id !== undefined ? [{ field: 'flow_id', to: flow_id, from: proposal.action.flow_id, at }] : []),
        ...(condition_value !== undefined ? [{ field: 'condition_value', to: condition_value, from: proposal.condition.value, at }] : []),
      ]
      const updated: Proposal = {
        ...proposal, ...fields, updated_at: at,
        action: flow_id === undefined ? proposal.action : { ...proposal.action, flow_id, flow_name: null },
        condition: { ...proposal.condition, value: condition_value ?? proposal.condition.value },
        edits: [...proposal.edits, ...changes],
      }
      proposals.set(updated.proposal_id, updated)
      return HttpResponse.json(updated)
    }),
    http.post(`${apiUrl}/proposals/:operation`, async ({ params, request }) => {
      const [id, action] = String(params.operation).split(':')
      const proposal = proposals.get(id)
      if (!proposal || (action !== 'approve' && action !== 'reject')) {
        return error(404, 'proposal_not_found', 'Proposal action not found.')
      }
      if (action === 'approve' && proposal.status === 'awaiting_publish') {
        return error(409, 'flow_not_published', 'Publish the flow in Adapty before continuing.')
      }
      const retryable = action === 'approve' && proposal.status === 'failed' && !proposal.adapty.ab_test_id
      if (proposal.status !== 'draft' && !retryable) return error(409, 'invalid_transition', 'This proposal cannot be approved or rejected.')
      if (action === 'approve') return HttpResponse.json(decide(proposal, proposal.action.needs_publish ? 'awaiting_publish' : 'live', action))
      const { reason } = await request.json() as { reason: string }
      return HttpResponse.json(decide(proposal, 'rejected', action, reason))
    }),
    http.get(`${appApiUrl}/settings`, () => HttpResponse.json(settings)),
    http.put(`${appApiUrl}/settings`, async ({ request }) => {
      settings = await request.json() as AppSettings
      return HttpResponse.json(settings)
    }),
    http.get(`${appApiUrl}/decisions`, ({ request }) => {
      const id = new URL(request.url).searchParams.get('proposal_id')
      return HttpResponse.json(decisions.filter((decision) => !id || id === decision.proposal_id))
    }),
    http.post(`${appApiUrl}/lookup`, async ({ request }) => {
      const { placement, customer_user_ids } = await request.json() as { placement: string; customer_user_ids: string[] }
      const live = [...proposals.values()].find((proposal) => proposal.status === 'live' && proposal.trigger_placement === placement)
      return HttpResponse.json({
        results: customer_user_ids.map((customer_user_id) => {
          const match = customer_user_id === freeUser ? live : undefined
          return {
            customer_user_id, segment_hash: match ? 'preview-targeted' : 'preview-default',
            flow_id: match?.action.flow_id ?? 'preview-default-flow', flow_name: match ? match.action.flow_name : 'Default flow',
          }
        }),
      })
    }),
  ]
}

export const handlers = createHandlers()
