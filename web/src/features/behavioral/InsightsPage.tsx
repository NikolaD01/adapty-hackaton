import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, appWrite, useAppQuery } from '../../shared/api'
import { QueryFeedback, RequestError } from '../../shared/ui/QueryFeedback'
import type { InsightRun, InsightSource, Proposal } from '../../types/targeting'
import { PlaceholderPage } from './PlaceholderPage'
import { Select } from '../../shared/ui/Select'
import { TargetingTable } from './TargetingTable'
import { ConditionList, NetEffect, outcomeWindow } from './TargetingDetails'
import { aboveThreshold, fieldLabel, times } from './plainLanguage'

const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

/** One sentence per confirmed signal and one line for the rest, above the detailed table. */
function SignalSummary({ rankings, days }: { rankings: InsightRun['rankings']; days?: number }) {
  const confirmed = rankings.filter((row) => row.passed)
  const rejected = rankings.filter((row) => !row.passed)
  const window = days ? ` over ${days} days` : ''
  return (
    <div className="insight-summary" aria-label="Summary">
      {confirmed.map((row) => (
        <p key={row.feature}>
          <strong>Confirmed:</strong> {aboveThreshold(row.feature, row.threshold)} bring{' '}
          <strong>{times(row.lift)}</strong> the net revenue of other users{window} (likely{' '}
          {times(row.ci_low)}–{times(row.ci_high)}). It also held on users the analysis did not see ({times(row.holdout_lift)}).
        </p>
      ))}
      {!confirmed.length && <p>No signal is confirmed yet.</p>}
      {!!rejected.length && (
        <p className="targeting-muted">Not confirmed: {rejected.map((row) => fieldLabel(row.feature)).join(', ')}.</p>
      )}
      <p className="targeting-muted">A confirmed signal shows who pays more, not why. The offer for each group comes from randomized tests.</p>
    </div>
  )
}

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
        {!!insight.rankings.length && <SignalSummary rankings={insight.rankings} days={days} />}
        <p className="targeting-muted">Details: revenue ratio of users above the threshold, with its likely range, and the same ratio on held-out users.</p>
        {!insight.rankings.length ? <p>No measured rankings.</p> : (
          <TargetingTable label="Ranked signals" headers={['Feature', 'Threshold', 'Direction', 'Lift (CI)', 'Holdout', 'Passed']}>
            {insight.rankings.map((row) => (
              <tr key={row.feature}>
                <th scope="row">{row.feature}</th>
                <td className="table-number">{number.format(row.threshold)}</td>
                <td>{row.direction}</td>
                <td><LiftInterval lift={row.lift} low={row.ci_low} high={row.ci_high} /></td>
                <td className="table-number">{number.format(row.holdout_lift)}×</td>
                <td><span className={`status-chip ${row.passed ? 'status-live' : 'status-failed'}`}>{row.passed ? 'Yes' : 'No'}</span></td>
              </tr>
            ))}
          </TargetingTable>
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
        {!!insight.uplift.length && (
          <TargetingTable label="Historical randomized uplift" headers={['Test', 'Segment', 'Compared arms', 'Net lift per user (CI)', 'Sample sizes']}>
            {insight.uplift.map((row) => (
              <tr key={`${row.segment_key}/${row.test}`}>
                <th scope="row">{row.test}</th>
                <td><code>{row.segment_key}</code></td>
                <td>{row.better_arm} vs {row.worse_arm}</td>
                <td><NetEffect value={row.diff_net_90d} interval={row} /></td>
                <td className="table-number">{number.format(row.n_a)} / {number.format(row.n_b)}</td>
              </tr>
            ))}
          </TargetingTable>
        )}
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
      <section className="behavioral-panel insight-toolbar">
        <div className="targeting-actions">
          <div className="inline-control">Requested source
            <Select<InsightSource> label="Requested source" value={source} disabled={run.isPending} onChange={setSource}
              options={[{ value: 'offline', label: 'Offline' }, { value: 'live', label: 'Live' }]} />
          </div>
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
