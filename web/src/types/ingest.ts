import type { Props } from 'feature-signal-sdk'

export interface Timeline {
  items: { event_id: string; key: string; occurred_at: string; props: Props }[]
}

export interface FeatureProfile {
  features: {
    feature: string
    name: string
    values: Record<string, number>
    tier: 'low' | 'mid' | 'high' | null
  }[]
}

export interface MetricRule {
  key: string
  name: string
  feature: string | null
  definition: { measure: string; window_days: number | null }
}

export interface MetricValues {
  items: { customer_user_id: string; rule_key: string; value: number }[]
}
