import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { apiUrl, appApiUrl, appWrite, request, useAppQuery } from '../../shared/api'
import { QueryFeedback, RequestError } from '../../shared/ui/QueryFeedback'
import { Select } from '../../shared/ui/Select'
import type { AppSettings, Decision, Mode, Proposal, ProposalPatch, ProposalStatus } from '../../types/targeting'
import { PlaceholderPage } from './PlaceholderPage'
import { ReviewList } from './ReviewList'
import { TargetingTable } from './TargetingTable'
import { ConditionList, outcomeWindow, showValue } from './TargetingDetails'
import { audienceLabel } from './plainLanguage'

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const SMALL_SAMPLE = 100

function signedUsd(value: number) {
  return `${value > 0 ? '+' : ''}${usd.format(value)}`
}

function offerName(proposal: Proposal) {
  const edited = proposal.edits.some((edit) => edit.field === 'flow_id')
  return !edited && proposal.action.flow_name ? `“${proposal.action.flow_name}”` : 'the chosen'
}

const statusLabels: Record<ProposalStatus, string> = {
  draft: 'Draft', approved: 'Approved', executing: 'Executing', awaiting_publish: 'Awaiting publish',
  live: 'Live', failed: 'Failed', rejected: 'Rejected',
}

function ModeSettings() {
  const query = useAppQuery<AppSettings>(['settings'], '/settings')
  const client = useQueryClient()
  const save = useMutation({
    mutationFn: (settings: AppSettings) => appWrite<AppSettings>('/settings', 'PUT', settings),
    onSuccess: (settings) => client.setQueryData(['settings'], settings),
    onSettled: () => client.invalidateQueries({ queryKey: ['settings'] }),
  })

  return (
    <section className="behavioral-panel review-mode">
      <div className="panel-heading">
        <div>
          <h2>Decision mode</h2>
          <p className="targeting-muted">Human: you approve, edit or reject every proposal. Autopilot: proposals start on their own, within limits.</p>
        </div>
        {query.data && (
          <div className="inline-control">
            <Select<Mode> label="Mode" value={query.data.mode} disabled={save.isPending}
              onChange={(mode) => save.mutate({ ...query.data!, mode })}
              options={[{ value: 'human', label: 'Human' }, { value: 'autopilot', label: 'Autopilot' }]} />
          </div>
        )}
      </div>
      <QueryFeedback {...query} />
      {query.data?.mode === 'autopilot' && (
        <p className="preview-notice" role="status">
          Autopilot starts tests by itself: at most {query.data.autopilot.max_live_proposals} at a time, and at
          least {query.data.autopilot.min_holdout_pct}% of every group keeps the current paywall. It only uses paywalls
          that are already published. A new paywall always waits for you to publish it in Adapty.
        </p>
      )}
      <RequestError error={save.error} />
    </section>
  )
}

function ProposalEdit({ proposal, onSave, onCancel, pending }: {
  proposal: Proposal
  onSave: (patch: ProposalPatch) => void
  onCancel: () => void
  pending: boolean
}) {
  const [validation, setValidation] = useState('')
  const initialCondition = JSON.stringify(proposal.condition.value)
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const patch: ProposalPatch = {}
    const holdout = Number(form.get('holdout_pct'))
    const cooldown = Number(form.get('cooldown_days'))
    const placement = String(form.get('trigger_placement')).trim()
    const flowId = String(form.get('flow_id')).trim()
    const condition = String(form.get('condition_value')).trim()
    if (!placement || !flowId) {
      setValidation('Enter a placement and a flow ID.')
      return
    }
    if (condition !== initialCondition) {
      try {
        const value: unknown = JSON.parse(condition)
        if (value === null || typeof value !== typeof proposal.condition.value
          || Array.isArray(value) !== Array.isArray(proposal.condition.value)) {
          throw new Error('Use the same JSON value type as the original condition.')
        }
        if (JSON.stringify(value) !== initialCondition) patch.condition_value = value
      } catch {
        setValidation('Enter a valid JSON value of the same type as the original condition.')
        return
      }
    }
    if (holdout !== proposal.holdout_pct) patch.holdout_pct = holdout
    if (cooldown !== proposal.cooldown_days) patch.cooldown_days = cooldown
    if (placement !== proposal.trigger_placement) patch.trigger_placement = placement
    if (flowId !== proposal.action.flow_id) patch.flow_id = flowId
    setValidation('')
    if (Object.keys(patch).length) onSave(patch)
    else onCancel()
  }

  return (
    <form onSubmit={submit} className="targeting-form">
      <fieldset disabled={pending}>
        <legend>Edit proposal</legend>
        <label>Holdout (%)<input name="holdout_pct" type="number" min="0" max="50" required defaultValue={proposal.holdout_pct} /></label>
        <label>Cooldown (days)<input name="cooldown_days" type="number" min="0" max="90" required defaultValue={proposal.cooldown_days} /></label>
        <label>Placement<input name="trigger_placement" required defaultValue={proposal.trigger_placement} /></label>
        <label>Flow ID<input name="flow_id" required defaultValue={proposal.action.flow_id} /></label>
        <label className="wide-field">Adapty condition value (JSON)<input name="condition_value" required defaultValue={initialCondition} /></label>
        {validation && <p role="alert" className="wide-field">{validation}</p>}
        <div className="targeting-actions wide-field">
          <button type="submit" className="primary-action">Save changes</button>
          <button type="button" onClick={onCancel}>Cancel</button>
        </div>
      </fieldset>
    </form>
  )
}

type ProposalChange = { action: 'edit'; patch: ProposalPatch } | { action: 'approve' } | { action: 'reject'; reason: string }

function ProposalCard({ proposal, activeEquivalent }: { proposal: Proposal; activeEquivalent?: Proposal }) {
  const client = useQueryClient()
  const history = useQuery({
    queryKey: ['decisions', proposal.proposal_id],
    queryFn: ({ signal }) => request<Decision[]>(`${appApiUrl}/decisions?proposal_id=${encodeURIComponent(proposal.proposal_id)}`, { signal }),
    enabled: proposal.status === 'failed',
  })
  const failure = history.data?.[0]?.steps.find((step) => !step.ok)
  const testAttempted = history.data?.some((decision) => decision.steps.some((step) =>
    step.step === 'ab_tests_create' || step.step === 'ab_tests_start'))
  const [form, setForm] = useState<'edit' | 'reject' | null>(null)
  const mutation = useMutation({
    mutationFn: (change: ProposalChange) => {
      const url = `${apiUrl}/proposals/${encodeURIComponent(proposal.proposal_id)}`
      if (change.action === 'edit') return request<Proposal>(url, { method: 'PATCH', body: JSON.stringify(change.patch) })
      return request<Proposal>(`${url}:${change.action}`, {
        method: 'POST', body: change.action === 'reject' ? JSON.stringify({ reason: change.reason }) : undefined,
      })
    },
    onSuccess: (updated) => {
      client.setQueryData<Proposal[]>(['proposals'], (list) => list?.map((item) => item.proposal_id === updated.proposal_id ? updated : item))
      setForm(null)
    },
    onSettled: () => Promise.all([
      client.invalidateQueries({ queryKey: ['proposals'] }),
      client.invalidateQueries({ queryKey: ['decisions'] }),
    ]),
  })

  function showForm(value: typeof form) {
    mutation.reset()
    setForm(value)
  }

  function reject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const reason = String(new FormData(event.currentTarget).get('reason')).trim()
    if (reason) mutation.mutate({ action: 'reject', reason })
  }

  const approving = mutation.isPending && mutation.variables?.action === 'approve'
  const days = outcomeWindow(proposal)
  const draft = proposal.status === 'draft'
  const awaitingPublish = proposal.status === 'awaiting_publish'
  const retryable = proposal.status === 'failed' && !proposal.adapty.ab_test_id && !testAttempted && !activeEquivalent
  const flowName = proposal.edits.some((edit) => edit.field === 'flow_id') ? null : proposal.action.flow_name
  const audience = audienceLabel(proposal)
  const { diff, ci_low: low, ci_high: high } = proposal.expected_effect
  const { n_a: nA, n_b: nB } = proposal.evidence
  const sample = typeof nA === 'number' && typeof nB === 'number' ? nA + nB : null
  const offerShare = 100 - proposal.holdout_pct
  return (
    <article className="behavioral-panel review-card" aria-label={audience}>
      <header className="review-card-heading">
        <div>
          <h2>{audience}</h2>
          <p>Offer: show them the {offerName(proposal)} paywall.</p>
        </div>
        <span className={`status-chip status-${approving ? 'executing' : proposal.status}`}>
          {approving ? 'Executing' : statusLabels[proposal.status]}
        </span>
      </header>
      <div className="review-body">
        <div className="review-outcome">
          <strong>Expected net revenue per user{days ? ` over ${days} days` : ''}</strong>
          <span>{signedUsd(diff)} <span className="targeting-muted">likely between {usd.format(low)} and {usd.format(high)}, net of refunds</span></span>
          {sample !== null && (
            <p className="targeting-muted">
              Based on {sample} users in a past randomized test{sample < SMALL_SAMPLE ? '. A small sample: treat it as uncertain.' : '.'}
            </p>
          )}
          {proposal.evidence.synthetic && <p className="targeting-muted">Synthetic demo data.</p>}
        </div>
        <p className="review-plain">
          Test: {offerShare}% of this group see the offer and {proposal.holdout_pct}% keep the current paywall, so the
          difference in revenue can be measured.
        </p>
        {awaitingPublish && <p className="preview-notice">Publish the new paywall in Adapty, then continue approval to start the test.</p>}
        {proposal.status === 'failed' && typeof failure?.detail.message === 'string' && (
          <p role="alert">Approval failed: {failure.detail.message}</p>
        )}
        {activeEquivalent && (
          <p>This audience already has this offer running.{' '}
            <Link to={`/dashboard/decisions?proposal_id=${encodeURIComponent(activeEquivalent.proposal_id)}`}>View active test</Link>
          </p>
        )}
        {form === 'edit' && draft && (
          <ProposalEdit proposal={proposal} onSave={(patch) => mutation.mutate({ action: 'edit', patch })}
            onCancel={() => showForm(null)} pending={mutation.isPending} />
        )}
        {form === 'reject' && draft && (
          <form className="targeting-form" onSubmit={reject}>
            <fieldset disabled={mutation.isPending}>
              <legend>Reject proposal</legend>
              <label className="wide-field">Reason<textarea name="reason" required maxLength={500} /></label>
              <div className="targeting-actions wide-field">
                <button type="submit">Confirm rejection</button>
                <button type="button" onClick={() => showForm(null)}>Cancel</button>
              </div>
            </fieldset>
          </form>
        )}
        {(draft || retryable || awaitingPublish || proposal.status === 'executing' || proposal.status === 'approved') && !form && (
          <div className="targeting-actions review-actions">
            <button type="button" className="primary-action"
              disabled={mutation.isPending || (!draft && !retryable && !awaitingPublish)}
              onClick={() => mutation.mutate({ action: 'approve' })}>
              {awaitingPublish ? 'Continue after publishing' : retryable ? 'Retry approval' : 'Approve'}
            </button>
            {draft && <>
              <button type="button" disabled={mutation.isPending} onClick={() => showForm('edit')}>Edit</button>
              <button type="button" disabled={mutation.isPending} onClick={() => showForm('reject')}>Reject</button>
            </>}
          </div>
        )}
        {proposal.decided_by && (
          <div className="targeting-actions review-actions">
            <Link to={`/dashboard/decisions?proposal_id=${encodeURIComponent(proposal.proposal_id)}`}>View decision log</Link>
            {proposal.status === 'live' && <Link to={`/dashboard/lookup?placement=${encodeURIComponent(proposal.trigger_placement)}`}>View audience and flows</Link>}
          </div>
        )}
        <RequestError error={mutation.error} />
        <details className="review-details">
          <summary>Technical details</summary>
          <h3>Analysis notes</h3>
          <p className="targeting-muted">{proposal.reason}</p>
          {proposal.evidence.uplift_test && <p className="targeting-muted">Evidence from {proposal.evidence.uplift_test}.</p>}
        <div className="review-facts">
          <section>
            <h3>Behavioral conditions</h3>
            <ConditionList conditions={proposal.evidence.segment_conditions ?? []} />
            <h3>Adapty filters</h3>
            <ConditionList conditions={[{ ...proposal.condition, field: proposal.condition.attribute }, ...proposal.adapty_filters]} />
          </section>
          <section>
            <h3>Paywall and test</h3>
            <dl className="targeting-facts">
              <dt>Placement</dt><dd>{proposal.trigger_placement}</dd>
              <dt>Offer flow</dt><dd>{flowName ? <>{flowName}<code className="data-key">{proposal.action.flow_id}</code></> : <code>{proposal.action.flow_id}</code>}</dd>
              {proposal.action.highlight_feature && <><dt>Highlights</dt><dd>{proposal.action.highlight_feature}</dd></>}
              <dt>Holdout</dt><dd>{proposal.holdout_pct}%</dd>
              <dt>Cooldown</dt><dd>{proposal.cooldown_days} days</dd>
              {proposal.decided_by && <><dt>Decided by</dt><dd>{proposal.decided_by === 'human' ? 'Human' : 'Autopilot'}</dd></>}
              {proposal.adapty.ab_test_id && <><dt>A/B test</dt><dd>{proposal.adapty.ab_test_id}</dd></>}
            </dl>
          </section>
        </div>
      {proposal.edits.length > 0 && (
        <section className="review-history">
          <h3>Edit history</h3>
          <TargetingTable label="Edit history" headers={['Field', 'Previous value', 'New value', 'Changed at']}>
            {proposal.edits.map((edit, index) => (
              <tr key={`${edit.at}-${index}`}>
                <th scope="row"><code>{edit.field}</code></th>
                <td>{showValue(edit.from)}</td>
                <td>{showValue(edit.to)}</td>
                <td><time dateTime={edit.at}>{new Date(edit.at).toLocaleString()}</time></td>
              </tr>
            ))}
          </TargetingTable>
        </section>
      )}
        </details>
      </div>
    </article>
  )
}

export function ProposalsPage() {
  const query = useAppQuery<Proposal[]>(['proposals'], '/proposals')
  const [selectedId, setSelectedId] = useState<string>()
  const items = query.data ?? []
  const selected = items.find((proposal) => proposal.proposal_id === selectedId) ?? items[0]

  return (
    <>
      <PlaceholderPage title="Proposals" description="Review the audience, offer and test before they go live in Adapty." />
      <ModeSettings />
      <QueryFeedback {...query} />
      {query.data?.length === 0 && <p className="behavioral-panel">No proposals yet. Run Insights to look for eligible offers.</p>}
      {selected && (
        <div className="review-layout">
          <ReviewList label="Proposal queue" selectedId={selected.proposal_id} onSelect={setSelectedId}
            items={items.map((proposal) => ({
              id: proposal.proposal_id,
              title: audienceLabel(proposal),
              description: `Offer: ${proposal.action.flow_name ?? 'chosen paywall'} · ${statusLabels[proposal.status]}`,
            }))} />
          <div className="review-records">
            {items.map((proposal) => (
              <div key={proposal.proposal_id} hidden={proposal.proposal_id !== selected.proposal_id}>
                <ProposalCard proposal={proposal} activeEquivalent={proposal.status === 'failed' ? items.find((other) =>
                  other.proposal_id !== proposal.proposal_id && ['live', 'executing', 'approved'].includes(other.status)
                  && other.trigger_placement === proposal.trigger_placement && other.segment_key === proposal.segment_key
                  && other.action.flow_id === proposal.action.flow_id) : undefined} />
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
