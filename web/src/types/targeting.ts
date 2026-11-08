export interface Predicate {
  field: string
  op: string
  value: unknown
}

interface Interval {
  ci_low: number
  ci_high: number
}

export type InsightSource = 'offline' | 'live'

export interface InsightRun {
  run_id: string
  source: InsightSource
  created_at: string
  rankings: (Interval & {
    feature: string; threshold: number; direction: 'up' | 'down'; lift: number
    holdout_lift: number; n_above: number; n_below: number; passed: boolean
  })[]
  tiers: { feature: string; rule_key: string; attribute: string; low_max: number; mid_max: number; passed: boolean }[]
  segments: (Interval & { segment_key: string; label: string; conditions: Predicate[]; size: number; net_arpu_90d: number })[]
  uplift: (Interval & {
    segment_key: string; test: string; better_arm: string; worse_arm: string; diff_net_90d: number; n_a: number; n_b: number
  })[]
  hypotheses: string[]
}

export const proposalStatuses = ['draft', 'approved', 'executing', 'awaiting_publish', 'live', 'failed', 'rejected'] as const
export type ProposalStatus = typeof proposalStatuses[number]
export type Mode = 'human' | 'autopilot'

export interface Proposal {
  proposal_id: string
  app_id: string
  status: ProposalStatus
  created_by: 'ai' | 'human'
  decided_by: Mode | null
  mode_at_decision: Mode | null
  trigger_placement: string
  segment_key: string
  condition: { attribute: string; op: string; value: unknown }
  adapty_filters: Predicate[]
  action: { type: 'flow'; flow_id: string; flow_name: string | null; highlight_feature: string | null; needs_publish: boolean }
  holdout_pct: number
  cooldown_days: number
  expected_effect: Interval & { metric: `net_revenue_${number}d`; diff: number }
  reason: string
  evidence: {
    run_id?: string; uplift_test?: string; outcome_window_days?: number; segment_conditions?: Predicate[]
    synthetic?: boolean; n_a?: number; n_b?: number
  }
  edits: { at: string; field: string; from: unknown; to: unknown }[]
  adapty: { segment_id: string | null; placement_id: string | null; ab_test_id: string | null; attributes_written: number }
  created_at: string
  updated_at: string
}

export interface ProposalPatch {
  holdout_pct?: number
  cooldown_days?: number
  trigger_placement?: string
  flow_id?: string
  condition_value?: unknown
}

export interface AppSettings {
  mode: Mode
  autopilot: { max_live_proposals: number; min_holdout_pct: number; allow_publish_flow: false }
}

export interface Decision {
  decision_id: string
  proposal_id: string
  decided_by: Mode
  action: 'approve' | 'reject' | 'autopilot_start'
  steps: { step: string; ok: boolean; detail: Record<string, unknown> }[]
  at: string
}

export interface LookupResult {
  customer_user_id: string
  segment_hash: string
  flow_id: string | null
  flow_name: string | null
  audience_name?: string | null
  ab_test_name?: string | null
  arms?: { flow_id: string | null; flow_name: string | null; weight: number; name: string | null }[]
}
