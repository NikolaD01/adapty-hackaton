import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { EventType, EventTypeInput, Feature, FeatureInput } from 'feature-signal-sdk'
import { useState, type FormEvent } from 'react'
import { appWrite, useAppQuery } from '../../shared/api'
import { QueryFeedback, RequestError } from '../../shared/ui/QueryFeedback'
import { demoUsers } from '../demo/demoActions'
import { useDemoProfile } from '../demo/DemoUserPanel'
import { PlaceholderPage } from './PlaceholderPage'

function CatalogFields({ type }: { type: 'feature' | 'event' }) {
  const maxKey = type === 'feature' ? 22 : 40
  return (
    <>
      <label>Key<input name="key" required minLength={2} maxLength={maxKey} pattern={`[a-z][a-z0-9_]{1,${maxKey - 1}}`} /></label>
      <label>Name<input name="name" required maxLength={100} /></label>
      <label className="wide-field">Description<textarea name="description" required maxLength={500} /></label>
    </>
  )
}

function catalogFields(data: FormData) {
  return {
    key: String(data.get('key')).trim(),
    name: String(data.get('name')).trim(),
    description: String(data.get('description')).trim(),
  }
}

function CatalogForm({ type, features = [] }: { type: 'feature' | 'event'; features?: Feature[] }) {
  const client = useQueryClient()
  const [validation, setValidation] = useState('')
  const save = useMutation({
    mutationFn: (input: FeatureInput | EventTypeInput) => appWrite<Feature | EventType>(
      type === 'feature' ? '/features' : '/event-types', 'POST', input,
    ),
    onSuccess: () => Promise.all([
      client.invalidateQueries({ queryKey: ['features'] }),
      client.invalidateQueries({ queryKey: ['event-types'] }),
      client.invalidateQueries({ queryKey: ['rules'] }),
      client.invalidateQueries({ queryKey: ['demo-user'] }),
    ]),
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const fields = catalogFields(data)
    if (!fields.name || !fields.description) {
      setValidation('Enter a name and description.')
      return
    }
    const featureKeys = data.getAll('features').map(String)
    if (featureKeys.length > 5) {
      setValidation('Select up to five features.')
      return
    }
    const plans = [...new Set(String(data.get('plans') ?? '').split(',').map((plan) => plan.trim()).filter(Boolean))]
    setValidation('')
    const payload = type === 'feature' ? { ...fields, plans } : { ...fields, features: featureKeys }
    save.mutate(payload, { onSuccess: () => form.reset() })
  }

  return (
    <details className="behavioral-panel">
      <summary>Add {type}</summary>
      <form onSubmit={submit} className="targeting-form">
        <fieldset disabled={save.isPending}>
          <legend>{type === 'feature' ? 'Feature details' : 'Event details'}</legend>
          <CatalogFields type={type} />
          {type === 'feature' ? (
            <label className="wide-field">Plans (comma-separated)<input name="plans" placeholder="premium, pro" /></label>
          ) : (
            <label className="wide-field">Features (up to five)
              <select name="features" multiple size={Math.min(5, Math.max(2, features.length))}>
                {features.map((feature) => <option key={feature.key} value={feature.key}>{feature.name}</option>)}
              </select>
            </label>
          )}
          {validation && <p role="alert" className="wide-field">{validation}</p>}
          <div className="targeting-actions wide-field">
            <button type="submit" className="primary-action">Save {type}</button>
          </div>
        </fieldset>
      </form>
      <RequestError error={save.error} />
      {save.isSuccess && <p role="status">{save.data.name} saved.</p>}
    </details>
  )
}

export function EventsPage() {
  const features = useAppQuery<Feature[]>(['features'], '/features')
  const events = useAppQuery<EventType[]>(['event-types'], '/event-types')
  const [userId, setUserId] = useState<string>(demoUsers[0].id)
  const profile = useDemoProfile(userId)

  return (
    <>
      <PlaceholderPage title="Events" description="Features and actions registered by your app." />
      <div className="targeting-grid">
        <CatalogForm type="feature" />
        <CatalogForm type="event" features={features.data} />
      </div>
      <section className="behavioral-panel">
        <header className="panel-heading">
          <h2>Features</h2>
          <label className="inline-control">
            Activity for
            <select value={userId} onChange={(event) => setUserId(event.target.value)}>
              {demoUsers.map((user) => <option key={user.id} value={user.id}>{user.label} · {user.id}</option>)}
            </select>
          </label>
        </header>
        <QueryFeedback {...features} />
        {profile.error && <RequestError error={profile.error} />}
        {features.data?.length === 0 && <p>No features registered.</p>}
        <ul>
          {features.data?.map((feature) => {
            const related = events.data?.filter((event) => event.features.includes(feature.key))
            const uses = profile.data?.features.find((item) => item.feature === feature.key)?.values[`${feature.key}_uses_7d`]
            return (
              <li key={feature.key} className="insight-detail">
                <strong>{feature.name}</strong> <code>{feature.key}</code>
                <div>{feature.description}</div>
                {!!feature.plans.length && <div>Plans · {feature.plans.join(', ')}</div>}
                <div>Uses in the last 7 days · {uses ?? '—'}</div>
                {related && <div>Events · {related.length ? related.map((event) => event.name).join(', ') : 'None registered'}</div>}
              </li>
            )
          })}
        </ul>
      </section>
      <section className="behavioral-panel">
        <h2>Event catalog</h2>
        <QueryFeedback {...events} />
        {events.data?.length === 0 && <p>No events registered.</p>}
        <ul>
          {events.data?.map((event) => (
            <li key={event.key}>
              <strong>{event.name}</strong> <code>{event.key}</code>
              <div>{event.description}</div>
              {event.features.length > 0 && <small>Features {event.features.join(', ')}</small>}
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}
