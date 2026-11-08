import type { EventType, Feature } from 'feature-signal-sdk'
import { blockedExport, demoUsers } from '../features/demo/demoActions'
import { webEnv } from '../shared/env'
import type { RuleSuggestions } from '../types/ingest'
import type { AppSettings, InsightRun, Proposal } from '../types/targeting'

export const seededAt = '2026-11-07T18:00:00Z'
export const freeUser = demoUsers[0].id
export const paidUser = demoUsers[1].id
export { blockedExport }

export const mockFeatures: Feature[] = [
  { key: 'background', name: 'Background removal', plans: [], description: 'Remove a photo background.', created_at: seededAt },
  { key: 'ai_enhance', name: 'AI enhance', plans: [], description: 'Apply an AI enhancement to a photo.', created_at: seededAt },
  { key: 'hd_export', name: 'Full-resolution export', plans: ['premium'], description: 'Export a photo in full resolution.', created_at: seededAt },
  { key: 'photo_import', name: 'Photo import', plans: [], description: 'Import a photo from the gallery.', created_at: seededAt },
]

export const mockEvents: EventType[] = [
  { key: 'photo_import', name: 'Photo imported', features: ['photo_import'], description: 'A photo was imported.' },
  { key: 'bg_remove', name: 'Background removed', features: ['background'], description: 'The photo background was removed.' },
  { key: 'ai_enhance', name: 'AI enhanced', features: ['ai_enhance'], description: 'An enhancement was applied.' },
  { key: 'export', name: 'Photo exported', features: [], description: 'A standard-resolution export completed.' },
  { key: 'export_hd_attempt', name: 'Full-resolution export tried', features: ['hd_export'], description: 'An HD export was requested.' },
  { key: blockedExport, name: 'Full-resolution export blocked', features: ['hd_export'], description: 'The free plan blocked an HD export.' },
].map((event, index) => ({ ...event, action_id: index + 1, created_at: seededAt }))

export const mockSuggestions: RuleSuggestions = {
  model: 'preview',
  suggestions: [{
    rule: {
      key: 'hd_export_blocked_7d', name: 'Blocked HD exports in 7 days', feature: 'hd_export',
      description: 'Counts attempts blocked by the plan in the past seven days.', source: 'ai', value_type: 'float',
      definition: { event_keys: [blockedExport], measure: 'count', window_days: 7 },
    },
    rationale: 'A blocked export may show demand for full-resolution output.',
  }],
}

const behavior = { field: 'ai_edits_first_day', op: '>=', value: 5 }
const subscription = { field: 'subscription_state', op: 'IN', value: ['never_subscribed'] }
const historicalTest = 'Main: 3 plans vs lifetime anchor (NA)'

export const mockInsight: InsightRun = {
  run_id: 'preview-lumen', source: 'offline', created_at: seededAt,
  rankings: [
    { feature: 'ai_edits_first_day', threshold: 5, direction: 'up', lift: 2.4, ci_low: 2.1, ci_high: 2.7, holdout_lift: 2.3, n_above: 13541, n_below: 36459, passed: true },
    { feature: 'photos_imported', threshold: 8, direction: 'up', lift: 1.03, ci_low: 0.94, ci_high: 1.1, holdout_lift: 1.01, n_above: 21000, n_below: 29000, passed: false },
  ],
  tiers: [{ feature: 'ai_enhance', rule_key: 'ai_enhance_uses_7d', attribute: 'f_ai_enhance_tier', low_max: 2, mid_max: 7, passed: true }],
  segments: [{ segment_key: 'power_editor', label: '5+ edits, no subscription', conditions: [behavior, subscription], size: 13541, net_arpu_90d: 15.57, ci_low: 14.9, ci_high: 16.2 }],
  uplift: [{ segment_key: 'power_editor', test: historicalTest, better_arm: 'main_lifetime', worse_arm: 'main', diff_net_90d: 14.4, ci_low: 9.1, ci_high: 19.8, n_a: 412, n_b: 398 }],
  hypotheses: [],
}

export const mockProposal: Proposal = {
  proposal_id: 'pr_preview', app_id: webEnv.appId, status: 'draft', created_by: 'ai', decided_by: null,
  mode_at_decision: null, trigger_placement: 'main', segment_key: 'power_editor',
  condition: { attribute: 'p_segment', op: 'IN', value: ['power_editor'] },
  adapty_filters: [subscription],
  action: { type: 'flow', flow_id: 'preview-lifetime', flow_name: 'Lifetime anchor', highlight_feature: null, needs_publish: false },
  holdout_pct: 20, cooldown_days: 7,
  expected_effect: { metric: 'net_revenue_90d', diff: 14.4, ci_low: 9.1, ci_high: 19.8 },
  reason: 'Users with 5+ edits gained more from the lifetime offer in the randomized Main test.',
  evidence: { run_id: mockInsight.run_id, uplift_test: historicalTest, segment_conditions: [behavior] },
  edits: [], adapty: { segment_id: null, placement_id: null, ab_test_id: null, attributes_written: 0 },
  created_at: seededAt, updated_at: seededAt,
}

export const mockSettings: AppSettings = {
  mode: 'human', autopilot: { max_live_proposals: 3, min_holdout_pct: 10, allow_publish_flow: false },
}
