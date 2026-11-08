import type { Predicate, Proposal } from '../../types/targeting'

/** Plain-language labels for the review screens. Technical keys stay available under "Technical details". */

const WORDS: Record<string, string> = { ai: 'AI', hd: 'HD', bg: 'background', ios: 'iOS', android: 'Android' }
const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

function words(key: string): string {
  return key.split('_').filter(Boolean).map((part) => WORDS[part] ?? part).join(' ')
}

function upperFirst(text: string): string {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text
}

/** Lower-case the first letter unless the first word is an acronym such as "AI". */
function lowerFirst(text: string): string {
  return text.length > 1 && text.charAt(1) === text.charAt(1).toLowerCase() ? text.charAt(0).toLowerCase() + text.slice(1) : text
}

type Usage = { feature: string; kind: 'uses' | 'days'; days: number | null }

/** `ai_enhance_uses_7d`, `ai_enhance_uses_total`, `ai_enhance_days_active_7d`: A's default rule keys. */
function usage(field: string): Usage | null {
  let match = /^(.+)_uses_(\d+)d$/.exec(field)
  if (match) return { feature: words(match[1]), kind: 'uses', days: Number(match[2]) }
  match = /^(.+)_uses_total$/.exec(field)
  if (match) return { feature: words(match[1]), kind: 'uses', days: null }
  match = /^(.+)_days_active_(\d+)d$/.exec(field)
  if (match) return { feature: words(match[1]), kind: 'days', days: Number(match[2]) }
  return null
}

export function fieldLabel(field: string): string {
  const use = usage(field)
  if (use?.kind === 'uses') return `${upperFirst(use.feature)} uses ${use.days ? `in ${use.days} days` : 'in total'}`
  if (use?.kind === 'days') return `${upperFirst(use.feature)} active days in ${use.days} days`
  const tier = /^f_(.+)_tier$/.exec(field)
  if (tier) return `${upperFirst(words(tier[1]))} level`
  return upperFirst(words(field))
}

/** Bounds of a whole-number count from conditions such as `> 0` and `<= 3` (counts and days are integers). */
function countRange(conditions: Predicate[]): { min: number | null; max: number | null } | null {
  let min: number | null = null
  let max: number | null = null
  for (const { op, value } of conditions) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return null
    if (op === '>') min = Math.max(min ?? -Infinity, Math.floor(value) + 1)
    else if (op === '>=') min = Math.max(min ?? -Infinity, Math.ceil(value))
    else if (op === '<=') max = Math.min(max ?? Infinity, Math.floor(value))
    else if (op === '<') max = Math.min(max ?? Infinity, Math.ceil(value) - 1)
    else if (op === '==') { min = value; max = value }
    else return null
  }
  return { min, max }
}

/** A verb phrase for a usage rule: "used AI enhance 1–3 times in 7 days". Null when the conditions are not counts. */
function usagePhrase(use: Usage, conditions: Predicate[]): string | null {
  const range = countRange(conditions)
  if (!range) return null
  const { min, max } = range
  if (use.kind === 'days') {
    const period = use.days ? ` of the last ${use.days} days` : ''
    if (max === 0) return `did not use ${use.feature}${period ? ` in the last ${use.days} days` : ''}`
    const span = min !== null && max !== null ? (min === max ? `${min}` : `${min}–${max}`) : min !== null ? `${min} or more` : `up to ${max}`
    return `used ${use.feature} on ${span}${period ? period : ' days'}`
  }
  const period = use.days ? ` in ${use.days} days` : ' in total'
  if (max === 0) return `did not use ${use.feature}${period}`
  if (min !== null && max === null && min <= 1) return `used ${use.feature} at least once${period}`
  const span = min !== null && max !== null ? (min === max ? `${min}` : `${min}–${max}`) : min !== null ? `${min} or more` : `up to ${max}`
  return `used ${use.feature} ${span} ${span === '1' ? 'time' : 'times'}${period}`
}

const OPS: Record<string, string> = { '>': 'above', '>=': 'at least', '<': 'below', '<=': 'at most' }

/** A noun phrase for any other condition: "subscription state never subscribed". */
function genericPhrase(field: string, conditions: Predicate[]): string {
  const label = lowerFirst(fieldLabel(field))
  return conditions.map(({ op, value }) => {
    if (op === 'IS NULL') return `no ${label}`
    if (op === 'IS NOT NULL') return `a ${label}`
    const shown = Array.isArray(value) ? value.map((item) => words(String(item))).join(' or ')
      : typeof value === 'number' ? number.format(value) : words(String(value))
    if (op === 'NOT IN') return `${label} other than ${shown}`
    return `${label} ${OPS[op] ? `${OPS[op]} ` : ''}${shown}`
  }).join(', ')
}

/** "Android users who used AI enhance 1–3 times in 7 days". Built only from the proposal's structured conditions. */
export function audienceLabel(proposal: Pick<Proposal, 'adapty_filters' | 'evidence'>): string {
  const platform = proposal.adapty_filters.find((filter) => filter.field === 'platform' && filter.op === 'IN')
  const platforms = Array.isArray(platform?.value) ? platform.value.map(String) : []
  const byField = new Map<string, Predicate[]>()
  for (const condition of [...(proposal.evidence.segment_conditions ?? []), ...proposal.adapty_filters]) {
    if (condition === platform) continue
    byField.set(condition.field, [...(byField.get(condition.field) ?? []), condition])
  }
  const verbs: string[] = []
  const nouns: string[] = []
  for (const [field, conditions] of byField) {
    const use = usage(field)
    const phrase = use && usagePhrase(use, conditions)
    if (phrase) verbs.push(phrase)
    else nouns.push(genericPhrase(field, conditions))
  }
  // Behavior first: it is what the group is about. The platform is a filter Adapty applies, so it goes last.
  if (!verbs.length && !nouns.length) return platforms.length ? `${platforms.join(' and ')} users` : 'Users'
  let label = 'Users'
  if (verbs.length) label += ` who ${verbs.join(' and ')}`
  if (nouns.length) label += `${verbs.length ? ',' : ''} with ${nouns.join(' and ')}`
  return platforms.length ? `${label} · ${platforms.join(' and ')}` : label
}

/** "users who used AI enhance at least once in 7 days", for a ranking threshold. */
export function aboveThreshold(field: string, threshold: number): string {
  const use = usage(field)
  const phrase = use && usagePhrase(use, [{ field, op: '>', value: threshold }])
  return phrase ? `users who ${phrase}` : `users with ${lowerFirst(fieldLabel(field))} above ${number.format(threshold)}`
}

export function times(value: number): string {
  return `${number.format(value)}×`
}
