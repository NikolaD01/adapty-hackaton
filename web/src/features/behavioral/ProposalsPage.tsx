import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { apiUrl, appWrite, request, useAppQuery } from '../../shared/api'
import { QueryFeedback, RequestError } from '../../shared/ui/QueryFeedback'
import type { AppSettings, Mode, Proposal, ProposalPatch, ProposalStatus } from '../../types/targeting'
import { PlaceholderPage } from './PlaceholderPage'
import { ConditionList, NetEffect, outcomeWindow, showValue } from './TargetingDetails'

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
    <section className="behavioral-panel">
      <h2>Decision mode</h2>
      <QueryFeedback {...query} />
      {query.data && <>
        <label className="inline-control">
          Mode
          <select value={query.data.mode} disabled={save.isPending}
            onChange={(event) => save.mutate({ ...query.data!, mode: event.target.value as Mode })}>
            <option value="human">Human</option>
            <option value="autopilot">Autopilot</option>
          </select>
        </label>
        {query.data.mode === 'autopilot' && (
          <p className="preview-notice" role="status">
            Autopilot can start eligible tests with published flows. Limit {query.data.autopilot.max_live_proposals} live proposals,
            minimum {query.data.autopilot.min_holdout_pct}% holdout. Publish new flows in Adapty.
          </p>
        )}
      </>}
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

function ProposalCard({ proposal }: { proposal: Proposal }) {
  const client = useQueryClient()
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
  const flowName = proposal.edits.some((edit) => edit.field === 'flow_id') ? null : proposal.action.flow_name
  return (
    <article className="behavioral-panel proposal-card" aria-label={proposal.segment_key}>
      <header className="panel-heading">
        <h2>{proposal.segment_key}</h2>
        <span className={`status-chip status-${approving ? 'executing' : proposal.status}`}>
          {approving ? 'Executing' : statusLabels[proposal.status]}
        </span>
      </header>
      <p>{proposal.reason}</p>
      <div className="targeting-grid">
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
            <dt>Offer flow</dt><dd>{flowName ? `${flowName} · ${proposal.action.flow_id}` : proposal.action.flow_id}</dd>
            {proposal.action.highlight_feature && <><dt>Highlights</dt><dd>{proposal.action.highlight_feature}</dd></>}
            <dt>Holdout</dt><dd>{proposal.holdout_pct}%</dd>
            <dt>Cooldown</dt><dd>{proposal.cooldown_days} days</dd>
            {proposal.decided_by && <><dt>Decided by</dt><dd>{proposal.decided_by === 'human' ? 'Human' : 'Autopilot'}</dd></>}
            {proposal.adapty.ab_test_id && <><dt>A/B test</dt><dd>{proposal.adapty.ab_test_id}</dd></>}
          </dl>
        </section>
      </div>
      <p><strong>Expected {days ? `${days}-day ` : ''}net revenue effect per user</strong> <NetEffect value={proposal.expected_effect.diff} interval={proposal.expected_effect} /></p>
      {proposal.evidence.uplift_test && <p>Evidence from {proposal.evidence.uplift_test}</p>}
      {proposal.edits.length > 0 && (
        <details>
          <summary>Edit history</summary>
          <ul>{proposal.edits.map((edit, index) => <li key={`${edit.at}-${index}`}>{edit.field} · {showValue(edit.from)} → {showValue(edit.to)}</li>)}</ul>
        </details>
      )}
      {awaitingPublish && <p className="preview-notice">Publish the new paywall in Adapty, then continue approval to start the test.</p>}
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
      {(draft || awaitingPublish || proposal.status === 'executing' || proposal.status === 'approved') && !form && (
        <div className="targeting-actions">
          <button type="button" className="primary-action"
            disabled={mutation.isPending || (!draft && !awaitingPublish)}
            onClick={() => mutation.mutate({ action: 'approve' })}>
            {awaitingPublish ? 'Continue after publishing' : 'Approve'}
          </button>
          {draft && <>
            <button type="button" disabled={mutation.isPending} onClick={() => showForm('edit')}>Edit</button>
            <button type="button" disabled={mutation.isPending} onClick={() => showForm('reject')}>Reject</button>
          </>}
        </div>
      )}
      {proposal.decided_by && (
        <div className="targeting-actions">
          <Link to={`/dashboard/decisions?proposal_id=${encodeURIComponent(proposal.proposal_id)}`}>View decision log</Link>
          {proposal.status === 'live' && <Link to={`/dashboard/lookup?placement=${encodeURIComponent(proposal.trigger_placement)}`}>View audience and flows</Link>}
        </div>
      )}
      <RequestError error={mutation.error} />
    </article>
  )
}

export function ProposalsPage() {
  const query = useAppQuery<Proposal[]>(['proposals'], '/proposals')
  return (
    <>
      <PlaceholderPage title="Proposals" description="Review the audience, offer and test before they go live in Adapty." />
      <ModeSettings />
      <QueryFeedback {...query} />
      {query.data?.length === 0 && <p className="behavioral-panel">No proposals yet. Run Insights to look for eligible offers.</p>}
      {query.data?.map((proposal) => <ProposalCard key={proposal.proposal_id} proposal={proposal} />)}
    </>
  )
}
