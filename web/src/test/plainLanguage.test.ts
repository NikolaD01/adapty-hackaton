import { expect, it } from 'vitest'
import { aboveThreshold, audienceLabel, fieldLabel } from '../features/behavioral/plainLanguage'

const uses = (op: string, value: number) => ({ field: 'ai_enhance_uses_7d', op, value })
const platform = (name: string) => ({ field: 'platform', op: 'IN', value: [name] })

it('describes the 60-day run segments in plain words', () => {
  expect(audienceLabel({ adapty_filters: [platform('Android')], evidence: { segment_conditions: [uses('<=', 3), uses('>', 0)] } }))
    .toBe('Users who used AI enhance 1–3 times in 7 days · Android')
  expect(audienceLabel({ adapty_filters: [platform('iOS')], evidence: { segment_conditions: [uses('>', 3)] } }))
    .toBe('Users who used AI enhance 4 or more times in 7 days · iOS')
  expect(audienceLabel({ adapty_filters: [platform('iOS')], evidence: { segment_conditions: [uses('<=', 0)] } }))
    .toBe('Users who did not use AI enhance in 7 days · iOS')
})

it('falls back to readable field names for other conditions', () => {
  expect(audienceLabel({
    adapty_filters: [{ field: 'subscription_state', op: 'IN', value: ['never_subscribed'] }],
    evidence: { segment_conditions: [{ field: 'ai_edits_first_day', op: '>=', value: 5 }] },
  })).toBe('Users with AI edits first day at least 5 and subscription state never subscribed')
  expect(audienceLabel({ adapty_filters: [], evidence: {} })).toBe('Users')
  expect(audienceLabel({ adapty_filters: [platform('Android')], evidence: {} })).toBe('Android users')
})

it('turns rule keys and thresholds into sentences', () => {
  expect(fieldLabel('photo_import_uses_7d')).toBe('Photo import uses in 7 days')
  expect(fieldLabel('hd_export_days_active_7d')).toBe('HD export active days in 7 days')
  expect(fieldLabel('f_ai_enhance_tier')).toBe('AI enhance level')
  expect(aboveThreshold('ai_enhance_uses_7d', 0)).toBe('users who used AI enhance at least once in 7 days')
  expect(aboveThreshold('background_uses_7d', 4)).toBe('users who used background 5 or more times in 7 days')
  expect(aboveThreshold('net_arpu', 2.5)).toBe('users with net arpu above 2.5')
})
