import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { appWrite } from '../../shared/api'
import { webEnv } from '../../shared/env'
import { RequestError } from '../../shared/ui/QueryFeedback'
import type { LookupResult } from '../../types/targeting'
import { demoUsers } from '../demo/demoActions'
import { PlaceholderPage } from './PlaceholderPage'

interface LookupInput {
  placement: string
  customer_user_ids: [string, string]
}

export function LookupPage() {
  const [params] = useSearchParams()
  const [validation, setValidation] = useState('')
  const lookup = useMutation({
    mutationFn: (input: LookupInput) => appWrite<{ results: LookupResult[] }>('/lookup', 'POST', input),
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const placement = String(form.get('placement')).trim()
    const first = String(form.get('first')).trim()
    const second = String(form.get('second')).trim()
    if (!placement || !first || !second || first === second) {
      setValidation('Enter a placement and two different customer user IDs.')
      return
    }
    setValidation('')
    lookup.mutate({ placement, customer_user_ids: [first, second] })
  }

  return (
    <>
      <PlaceholderPage title="Lookup" description="Compare the flows served to two users at the same placement." />
      <form className="targeting-form" onSubmit={submit}>
        <fieldset disabled={lookup.isPending}>
          <legend>Adapty flow lookup</legend>
          <label className="wide-field">Placement
            <input name="placement" required defaultValue={params.get('placement') ?? (webEnv.useMocks ? 'main' : 'ai_limit_reached')} />
          </label>
          <label>First customer user ID<input name="first" required maxLength={128} defaultValue={demoUsers[0].id} /></label>
          <label>Second customer user ID<input name="second" required maxLength={128} defaultValue={demoUsers[1].id} /></label>
          <div className="targeting-actions wide-field">
            <button className="primary-action" type="submit">{lookup.isPending ? 'Looking up…' : 'Compare flows'}</button>
          </div>
        </fieldset>
      </form>
      {validation && <p role="alert">{validation}</p>}
      <RequestError error={lookup.error} />
      {lookup.data && lookup.variables && (
        <section className="behavioral-panel" aria-label="Lookup results">
          <h2>Results for {lookup.variables.placement}</h2>
          <p>Adapty assigns the test arm. A user inside the segment can receive the same flow as a user outside it.</p>
          <div className="targeting-grid">
            {lookup.variables.customer_user_ids.map((id) => {
              const result = lookup.data.results.find((item) => item.customer_user_id === id)
              return (
                <article className="lookup-result" key={id}>
                  <h3>{id}</h3>
                  {result ? (
                    <dl className="targeting-facts">
                      <dt>Flow name</dt><dd>{result.flow_name ?? '—'}</dd>
                      <dt>Flow ID</dt><dd>{result.flow_id ?? '—'}</dd>
                      <dt>Segment hash</dt><dd>{result.segment_hash || '—'}</dd>
                    </dl>
                  ) : <p>No lookup result returned for this user.</p>}
                </article>
              )
            })}
          </div>
        </section>
      )}
    </>
  )
}
