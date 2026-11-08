import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, appWrite, useAppQuery } from '../../shared/api'
import { QueryFeedback, RequestError } from '../../shared/ui/QueryFeedback'
import type { InsightRun, InsightSource, Proposal } from '../../types/targeting'
import { PlaceholderPage } from './PlaceholderPage'
import { ConditionList, NetEffect, outcomeWindow } from './TargetingDetails'

const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

function LiftInterval({ lift, low, high }: { lift: number; low: number; high: number }) {
  const min = Math.min(low, lift, 1)
  const max = Math.max(high, lift, 1)
  const range = max - min || 1
  const position = (value: number) => 5 + 90 * (value - min) / range
  return (
    <>
      <strong>{number.format(lift)}×</strong> <span className="targeting-muted">({number.format(low)}–{number.format(high)}×)</span>
      <span className="ci-track" aria-hidden="true">
        <span className="ci-neutral" style={{ left: `${position(1)}%` }} />
        <span className="ci-range" style={{ left: `${position(low)}%`, width: `${Math.max(position(high) - position(low), 1)}%` }} />
        <span className="ci-point" style={{ left: `${position(lift)}%` }} />
      </span>
    </>
  )
}

function Results({ insight }: { insight: InsightRun }) {
  const proposals = useAppQuery<Proposal[]>(['proposals'], '/proposals')
  // InsightRun retains legacy field names even when the server uses a different window.
  const evidence = proposals.data?.find((proposal) => proposal.evidence.run_id === insight.run_id)
  const days = evidence && outcomeWindow(evidence)
  return (
    <>
      <p className="insight-source" role="status">
        Actual source <strong>{insight.source}</strong> · <time dateTime={insight.created_at}>{new Date(insight.created_at).toLocaleString()}</time>
      </p>
      <section className="behavioral-panel">
        <h2>Ranked signals</h2>
        <p className="targeting-muted">Net revenue ratio with training confidence interval and separate holdout check.</p>
        {!insight.rankings.length ? <p>No measured rankings.</p> : (
          <div className="table-scroll">
            <table className="targeting-table">
              <thead><tr><th>Feature</th><th>Threshold</th><th>Direction</th><th>Lift (CI)</th><th>Holdout</th><th>Passed</th></tr></thead>
              <tbody>{insight.rankings.map((row) => (
                <tr key={row.feature}>
                  <th scope="row">{row.feature}</th>
                  <td>{number.format(row.threshold)}</td>
                  <td>{row.direction}</td>
                  <td><LiftInterval lift={row.lift} low={row.ci_low} high={row.ci_high} /></td>
                  <td>{number.format(row.holdout_lift)}×</td>
                  <td><span className={`status-chip ${row.passed ? 'status-live' : 'status-failed'}`}>{row.passed ? 'Yes' : 'No'}</span></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>
      <div className="targeting-grid">
        <section className="behavioral-panel">
          <h2>Feature tiers</h2>
          {!insight.tiers.length && <p>No tiers in this run.</p>}
          <ul>{insight.tiers.map((tier) => (
            <li key={tier.feature}>
              <strong>{tier.feature}</strong> <code>{tier.rule_key}</code>
              <p>Low ≤ {tier.low_max} · Mid ≤ {tier.mid_max} · High &gt; {tier.mid_max}</p>
              <p>{tier.passed ? <>Adapty attribute <code>{tier.attribute}</code></> : 'Did not pass measurement'}</p>
            </li>
          ))}</ul>
        </section>
        <section className="behavioral-panel">
          <h2>Hypotheses</h2>
          {!insight.hypotheses.length && <p>No unmeasured rules in this run.</p>}
          <ul>{insight.hypotheses.map((rule) => (
            <li key={rule}><code>{rule}</code><p>Not measured yet · candidate for an A/B test</p></li>
          ))}</ul>
        </section>
      </div>
      <section className="behavioral-panel">
        <h2>Candidate segments</h2>
        {!insight.segments.length && <p>No measured segments.</p>}
        {insight.segments.map((segment) => (
          <article key={segment.segment_key} className="insight-detail">
            <h3>{segment.label}</h3>
            <p>{number.format(segment.size)} users · <NetEffect value={segment.net_arpu_90d} interval={segment} /> per user, net of refunds</p>
            <ConditionList conditions={segment.conditions} />
          </article>
        ))}
      </section>
      <section className="behavioral-panel">
        <h2>Historical randomized uplift</h2>
        <p className="targeting-muted">Prior A/B arms · difference in {days ? `${days}-day ` : ''}net revenue per user, after refunds.</p>
        {!insight.uplift.length && <p>No randomized comparisons in this run.</p>}
        {insight.uplift.map((row) => (
          <article key={`${row.segment_key}/${row.test}`} className="insight-detail">
            <h3>{row.test}</h3>
            <p>{row.segment_key} · {row.better_arm} vs {row.worse_arm}</p>
            <p><NetEffect value={row.diff_net_90d} interval={row} /> per user · {row.n_a} and {row.n_b} users</p>
          </article>
        ))}
      </section>
    </>
  )
}

export function InsightsPage() {
  const client = useQueryClient()
  const [source, setSource] = useState<InsightSource>('offline')
  const latest = useAppQuery<InsightRun>(['insights', 'latest'], '/insights/latest')
  const run = useMutation({
    mutationFn: () => appWrite<InsightRun>('/insights:run', 'POST', { source }),
    onSuccess: async (insight) => {
      await client.cancelQueries({ queryKey: ['insights', 'latest'] })
      client.setQueryData(['insights', 'latest'], insight)
      await Promise.all([
        client.invalidateQueries({ queryKey: ['proposals'] }),
        client.invalidateQueries({ queryKey: ['decisions'] }),
        client.invalidateQueries({ queryKey: ['demo-user'] }),
      ])
    },
  })
  const noRun = latest.error instanceof ApiError && latest.error.code === 'insight_not_found'

  return (
    <>
      <PlaceholderPage title="Insights" description="Review which behavioral signals hold on unseen users and which offers have randomized evidence." />
      <section className="behavioral-panel">
        <div className="targeting-actions">
          <label className="inline-control">Requested source
            <select value={source} disabled={run.isPending} onChange={(event) => setSource(event.target.value as InsightSource)}>
              <option value="offline">Offline</option>
              <option value="live">Live</option>
            </select>
          </label>
          <button className="primary-action" disabled={run.isPending} onClick={() => run.mutate()}>
            {run.isPending ? 'Running…' : 'Run insights'}
          </button>
        </div>
        <RequestError error={run.error} />
        {noRun ? <p>No insight run yet.</p> : <QueryFeedback {...latest} />}
      </section>
      {latest.data && <Results insight={latest.data} />}
    </>
  )
}
