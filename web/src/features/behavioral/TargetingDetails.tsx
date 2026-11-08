import type { Predicate } from '../../types/targeting'

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export function showValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(showValue).join(', ')
  return typeof value === 'string' ? value : JSON.stringify(value) ?? '—'
}

export function ConditionList({ conditions }: { conditions: Predicate[] }) {
  if (!conditions.length) return <p>None provided.</p>
  return <ul>{conditions.map(({ field, op, value }, index) => (
    <li key={`${field}-${index}`}><code>{field}</code> {op}{value != null && ` ${showValue(value)}`}</li>
  ))}</ul>
}

export function NetEffect({ value, interval }: { value: number; interval: { ci_low: number; ci_high: number } }) {
  return <span>{usd.format(value)} <span className="targeting-muted">(CI {usd.format(interval.ci_low)} to {usd.format(interval.ci_high)})</span></span>
}
