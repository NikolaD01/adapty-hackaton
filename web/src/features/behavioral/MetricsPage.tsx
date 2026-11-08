import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { appWrite, useAppQuery } from '../../shared/api'
import { QueryFeedback, RequestError } from '../../shared/ui/QueryFeedback'
import type { MetricRule, MetricValues, RuleInput, RuleSuggestions } from '../../types/ingest'
import { PlaceholderPage } from './PlaceholderPage'
import { TargetingTable } from './TargetingTable'

function Suggestions() {
  const client = useQueryClient()
  const [suggestions, setSuggestions] = useState<RuleSuggestions['suggestions']>([])
  const suggest = useMutation({
    mutationFn: () => appWrite<RuleSuggestions>('/rules:suggest', 'POST'),
    onSuccess: (result) => setSuggestions(result.suggestions),
  })

  function dismiss(key: string) {
    setSuggestions((previous) => previous.filter(({ rule }) => rule.key !== key))
  }

  const accept = useMutation({
    mutationFn: (rule: RuleInput) => appWrite<MetricRule>('/rules', 'POST', rule),
    onSuccess: (saved) => {
      dismiss(saved.key)
      return client.invalidateQueries({ queryKey: ['rules'] })
    },
  })
  const busy = suggest.isPending || accept.isPending

  return (
    <section className="behavioral-panel">
      <header className="panel-heading">
        <h2>AI rule suggestions</h2>
        <div className="targeting-actions">
          <button className="primary-action" disabled={busy} onClick={() => { accept.reset(); suggest.mutate() }}>
            {suggest.isPending ? 'Suggesting…' : 'Suggest with AI'}
          </button>
        </div>
      </header>
      <RequestError error={suggest.error ?? accept.error} />
      {suggest.isSuccess && suggest.data.suggestions.length === 0 && <p>No rule suggestions for this catalog.</p>}
      {suggestions.map(({ rule, rationale }) => (
        <article key={rule.key} className="insight-detail">
          <h3>{rule.name}</h3>
          <p>{rationale}</p>
          <p><code>{rule.definition.measure}({rule.definition.event_keys.join(', ')})</code>
            {rule.definition.window_days ? ` · ${rule.definition.window_days} days` : ' · all history'}</p>
          <div className="targeting-actions">
            <button disabled={busy} onClick={() => accept.mutate(rule)}>Accept</button>
            <button disabled={busy} onClick={() => dismiss(rule.key)}>Dismiss</button>
          </div>
        </article>
      ))}
    </section>
  )
}

export function MetricsPage() {
  const rules = useAppQuery<MetricRule[]>(['rules'], '/rules')
  const values = useAppQuery<MetricValues>(['values'], '/values?limit=20')

  return (
    <>
      <PlaceholderPage title="Metrics" description="Metrics turn tracked events into values you can use in rules." />
      <Suggestions />
      <section className="behavioral-panel">
        <h2>Rules</h2>
        <QueryFeedback {...rules} />
        {rules.data?.length === 0 && <p>No rules configured.</p>}
        {!!rules.data?.length && (
          <TargetingTable label="Rules" headers={['Rule', 'Measure', 'Window', 'Source']}>
            {rules.data.map((rule) => (
              <tr key={rule.key}>
                <th scope="row"><span>{rule.name}</span><code className="data-key">{rule.key}</code></th>
                <td>{rule.definition.measure}</td>
                <td>{rule.definition.window_days ? `${rule.definition.window_days} days` : 'All history'}</td>
                <td><span className="data-tag">{rule.source === 'ai' ? 'AI' : rule.source}</span></td>
              </tr>
            ))}
          </TargetingTable>
        )}
      </section>
      <section className="behavioral-panel">
        <h2>Sample values</h2>
        <QueryFeedback {...values} />
        {values.data?.items.length === 0 && <p>No values computed.</p>}
        {!!values.data?.items.length && (
          <TargetingTable label="Sample values" headers={['Rule', 'Customer user ID', 'Value']}>
            {values.data.items.map((item) => (
              <tr key={`${item.customer_user_id}/${item.rule_key}`}>
                <th scope="row"><code>{item.rule_key}</code></th>
                <td><code>{item.customer_user_id}</code></td>
                <td className="table-number">{item.value}</td>
              </tr>
            ))}
          </TargetingTable>
        )}
      </section>
    </>
  )
}
