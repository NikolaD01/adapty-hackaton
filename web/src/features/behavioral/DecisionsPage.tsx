import { useSearchParams } from 'react-router-dom'
import { useAppQuery } from '../../shared/api'
import { QueryFeedback } from '../../shared/ui/QueryFeedback'
import type { Decision } from '../../types/targeting'
import { PlaceholderPage } from './PlaceholderPage'
import { TargetingTable } from './TargetingTable'
import { showValue } from './TargetingDetails'

const actions: Record<Decision['action'], string> = { approve: 'Approved', reject: 'Rejected', autopilot_start: 'Started by Autopilot' }

export function DecisionsPage() {
  const [params, setParams] = useSearchParams()
  const proposalId = params.get('proposal_id')
  const path = proposalId ? `/decisions?proposal_id=${encodeURIComponent(proposalId)}` : '/decisions'
  const decisions = useAppQuery<Decision[]>(['decisions', proposalId ?? ''], path)
  return (
    <>
      <PlaceholderPage title="Decisions" description="Review who made each decision and what happened in Adapty." />
      {proposalId && (
        <div className="targeting-actions">
          <p>Showing <code>{proposalId}</code></p>
          <button onClick={() => setParams({})}>Show all decisions</button>
        </div>
      )}
      <QueryFeedback {...decisions} />
      {decisions.data?.length === 0 && <p className="behavioral-panel">No decisions recorded.</p>}
      {decisions.data?.map((decision) => (
        <article key={decision.decision_id} className="behavioral-panel">
          <header className="panel-heading">
            <h2>{actions[decision.action]} · {decision.proposal_id}</h2>
            <span className="status-chip">{decision.decided_by === 'human' ? 'Human' : 'Autopilot'}</span>
          </header>
          <p className="targeting-muted"><time dateTime={decision.at}>{new Date(decision.at).toLocaleString()}</time></p>
          {decision.steps.length > 0 && (
            <TargetingTable label="Decision steps" headers={['Step', 'Result', 'Details']}>
              {decision.steps.map((step, index) => (
                <tr key={`${step.step}-${index}`}>
                  <th scope="row"><code>{step.step}</code></th>
                  <td><span className={`status-chip ${step.ok ? 'status-live' : 'status-failed'}`}>{step.ok ? 'OK' : 'Failed'}</span></td>
                  <td>
                    {!Object.keys(step.detail).length && '—'}
                    {Object.entries(step.detail).map(([name, value]) => (
                      <div key={name} className="step-detail"><strong>{name}</strong> · {showValue(value)}</div>
                    ))}
                  </td>
                </tr>
              ))}
            </TargetingTable>
          )}
        </article>
      ))}
    </>
  )
}
