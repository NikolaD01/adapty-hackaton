import { useAppQuery } from '../../shared/api'
import { QueryFeedback } from '../../shared/ui/QueryFeedback'
import type { MetricRule, MetricValues } from '../../types/ingest'
import { PlaceholderPage } from './PlaceholderPage'

export function MetricsPage() {
  const rules = useAppQuery<MetricRule[]>(['rules'], '/rules')
  const values = useAppQuery<MetricValues>(['values'], '/values?limit=20')

  return (
    <>
      <PlaceholderPage title="Metrics" description="Metrics turn tracked events into values you can use in rules." />
      <section className="behavioral-panel">
        <h2>Rules</h2>
        <QueryFeedback {...rules} />
        {rules.data?.length === 0 && <p>No rules configured.</p>}
        {rules.data && (
          <ul>
            {rules.data.map((rule) => (
              <li key={rule.key}>
                <strong>{rule.name}</strong> <code>{rule.key}</code>
                <div>{rule.definition.measure}{rule.definition.window_days && ` · ${rule.definition.window_days} days`}</div>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="behavioral-panel">
        <h2>Sample values</h2>
        <QueryFeedback {...values} />
        {values.data?.items.length === 0 && <p>No values computed.</p>}
        {values.data && (
          <ul>
            {values.data.items.map((item) => (
              <li key={`${item.customer_user_id}/${item.rule_key}`}>
                <strong>{item.value}</strong> <code>{item.rule_key}</code>
                <div>{item.customer_user_id}</div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
