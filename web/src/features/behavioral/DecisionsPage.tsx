import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAppQuery } from '../../shared/api'
import { QueryFeedback } from '../../shared/ui/QueryFeedback'
import type { Decision } from '../../types/targeting'
import { PlaceholderPage } from './PlaceholderPage'
import { ReviewList } from './ReviewList'
import { TargetingTable } from './TargetingTable'
import { showValue } from './TargetingDetails'

const actions: Record<Decision['action'], string> = { approve: 'Approved', reject: 'Rejected', autopilot_start: 'Started by Autopilot' }
const actor = { human: 'Human', autopilot: 'Autopilot' }
const timestamp = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' })

function DecisionDetails({ decision }: { decision: Decision }) {
  const failed = decision.steps.filter((step) => !step.ok).length
  return (
    <article className="behavioral-panel review-card">
      <header className="review-card-heading">
        <div>
          <h2>{actions[decision.action]}</h2>
          <p><code>{decision.proposal_id}</code> <time dateTime={decision.at}>{timestamp.format(new Date(decision.at))}</time></p>
        </div>
        <span className="status-chip">{actor[decision.decided_by]}</span>
      </header>
      <section className="review-body">
        <div className="panel-heading">
          <h3>Execution steps</h3>
          {decision.steps.length > 0 && (
            <span className={`status-chip ${failed ? 'status-failed' : 'status-live'}`}>
              {failed ? `${failed} failed` : `${decision.steps.length} completed`}
            </span>
          )}
        </div>
        {decision.steps.length ? (
          <TargetingTable label="Decision steps" headers={['Step', 'Result', 'Details']}>
            {decision.steps.map((step, index) => (
              <tr key={`${step.step}-${index}`}>
                <th scope="row"><code>{step.step}</code></th>
                <td><span className={`status-chip ${step.ok ? 'status-live' : 'status-failed'}`}>{step.ok ? 'OK' : 'Failed'}</span></td>
                <td>
                  {Object.keys(step.detail).length ? (
                    <dl className="decision-step-details">
                      {Object.entries(step.detail).map(([name, value]) => (
                        <div key={name}><dt>{name.replaceAll('_', ' ')}</dt><dd>{showValue(value)}</dd></div>
                      ))}
                    </dl>
                  ) : '—'}
                </td>
              </tr>
            ))}
          </TargetingTable>
        ) : <p className="targeting-muted">No execution steps recorded.</p>}
      </section>
    </article>
  )
}

export function DecisionsPage() {
  const [params, setParams] = useSearchParams()
  const [selectedId, setSelectedId] = useState<string>()
  const proposalId = params.get('proposal_id')
  const path = proposalId ? `/decisions?proposal_id=${encodeURIComponent(proposalId)}` : '/decisions'
  const decisions = useAppQuery<Decision[]>(['decisions', proposalId ?? ''], path)
  const items = decisions.data ?? []
  const selected = items.find((decision) => decision.decision_id === selectedId) ?? items[0]

  return (
    <>
      <PlaceholderPage title="Decisions" description="See who made each decision and what ran in Adapty." />
      {proposalId && (
        <div className="behavioral-panel review-filter">
          <p>Proposal <code>{proposalId}</code></p>
          <div className="targeting-actions"><button type="button" onClick={() => setParams({})}>Show all decisions</button></div>
        </div>
      )}
      <QueryFeedback {...decisions} />
      {decisions.data?.length === 0 && <p className="behavioral-panel">No decisions recorded.</p>}
      {selected && (
        <div className="review-layout">
          <ReviewList label="Decision history" selectedId={selected.decision_id} onSelect={setSelectedId}
            items={items.map((decision) => ({
              id: decision.decision_id,
              title: actions[decision.action],
              description: `${decision.proposal_id} · ${timestamp.format(new Date(decision.at))}`,
              badge: decision.steps.some((step) => !step.ok)
                ? <span className="status-chip status-failed">Step failed</span>
                : undefined,
            }))} />
          <DecisionDetails decision={selected} />
        </div>
      )}
    </>
  )
}
