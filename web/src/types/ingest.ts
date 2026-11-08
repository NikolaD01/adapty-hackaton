import type { Props, PropValue } from 'feature-signal-sdk'

export interface Timeline {
  customer_user_id: string
  items: { event_id: string; key: string; occurred_at: string; received_at: string; props: Props }[]
}

export interface FeatureProfile {
  customer_user_id: string
  features: {
    feature: string
    name: string
    values: Record<string, number>
    tier: 'low' | 'mid' | 'high' | null
    computed_at?: string | null
  }[]
}

export interface RuleInput {
  key: string
  name: string
  description: string
  feature?: string | null
  source: 'human' | 'ai' | 'default'
  value_type: 'float'
  definition: {
    event_keys: string[]
    measure: 'count' | 'distinct' | 'exists' | 'days_active' | 'ratio' | 'sum' | 'last' | 'max' | 'min'
    window_days?: number | null
    distinct_prop?: string | null
    value_prop?: string | null
    denominator_event_keys?: string[] | null
    where?: { prop: string; op: 'eq' | 'lt' | 'lte' | 'gt' | 'gte'; value: Exclude<PropValue, null> } | null
  }
}

export interface MetricRule extends RuleInput {
  rule_id: number
  created_at: string
}

export interface MetricValues {
  items: { customer_user_id: string; rule_key: string; value: number; computed_at: string }[]
  next_cursor: string | null
}

export interface RuleSuggestions {
  suggestions: { rule: RuleInput; rationale: string }[]
  model: string
}
