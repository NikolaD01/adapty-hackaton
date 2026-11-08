import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { EventType, EventTypeInput, Feature, FeatureInput } from 'feature-signal-sdk'
import { useRef, useState, type FormEvent } from 'react'
import { appWrite, useAppQuery } from '../../shared/api'
import { QueryFeedback, RequestError } from '../../shared/ui/QueryFeedback'
import { demoUsers } from '../demo/demoActions'
import { useDemoProfile } from '../demo/DemoUserPanel'
import { PlaceholderPage } from './PlaceholderPage'
import { TargetingTable } from './TargetingTable'

type CatalogType = 'feature' | 'event'

function CatalogFields({ type }: { type: CatalogType }) {
  const maxKey = type === 'feature' ? 22 : 40
  return (
    <>
      <label>Key<input name="key" required minLength={2} maxLength={maxKey} pattern={`[a-z][a-z0-9_]{1,${maxKey - 1}}`} autoFocus /></label>
      <label>Name<input name="name" required maxLength={100} /></label>
      <label className="wide-field">Description<textarea name="description" required maxLength={500} rows={2} /></label>
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

function CatalogForm({ type, features = [], onCancel }: { type: CatalogType; features?: Feature[]; onCancel: () => void }) {
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
    <section className="behavioral-panel catalog-editor" id="catalog-editor">
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
            <button type="button" onClick={onCancel}>Cancel</button>
          </div>
        </fieldset>
      </form>
      <RequestError error={save.error} />
      {save.isSuccess && <p className="save-feedback" role="status">{save.data.name} saved.</p>}
    </section>
  )
}

export function EventsPage() {
  const features = useAppQuery<Feature[]>(['features'], '/features')
  const events = useAppQuery<EventType[]>(['event-types'], '/event-types')
  const [userId, setUserId] = useState<string>(demoUsers[0].id)
  const [form, setForm] = useState<CatalogType | null>(null)
  const opener = useRef<HTMLButtonElement | null>(null)
  const profile = useDemoProfile(userId)
  const featureNames = new Map(features.data?.map(({ key, name }) => [key, name]))

  return (
    <>
      <PlaceholderPage title="Events" description="Manage the events and features used by behavioral targeting." actions={
        <>
          <button type="button" aria-expanded={form === 'feature'} aria-controls={form === 'feature' ? 'catalog-editor' : undefined} onClick={(event) => {
            opener.current = event.currentTarget
            setForm('feature')
          }}>Add feature</button>
          <button type="button" className="primary-action" aria-expanded={form === 'event'} aria-controls={form === 'event' ? 'catalog-editor' : undefined} onClick={(event) => {
            opener.current = event.currentTarget
            setForm('event')
          }}>Add event</button>
        </>
      } />
      {form && <CatalogForm key={form} type={form} features={features.data} onCancel={() => {
        setForm(null)
        opener.current?.focus()
      }} />}
      <section className="behavioral-panel">
        <header className="panel-heading">
          <div><h2>Features</h2><p className="targeting-muted">Usage is scoped to the selected profile.</p></div>
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
        {!!features.data?.length && (
          <TargetingTable label="Features" headers={['Feature', 'Events', 'Plans', '7-day uses']}>
            {features.data.map((feature) => {
              const related = events.data?.filter((event) => event.features.includes(feature.key))
              const uses = profile.data?.features.find((item) => item.feature === feature.key)?.values[`${feature.key}_uses_7d`]
              return (
                <tr key={feature.key}>
                  <th scope="row"><span>{feature.name}</span><code className="data-key">{feature.key}</code><span className="table-note">{feature.description}</span></th>
                  <td>{related?.length ? related.map((event) => event.name).join(', ') : '—'}</td>
                  <td><div className="data-tags">{feature.plans.length ? feature.plans.map((plan) => <span className="data-tag" key={plan}>{plan}</span>) : '—'}</div></td>
                  <td className="table-number">{uses ?? '—'}</td>
                </tr>
              )
            })}
          </TargetingTable>
        )}
      </section>
      <section className="behavioral-panel">
        <header className="panel-heading"><h2>Event catalog</h2></header>
        <QueryFeedback {...events} />
        {events.data?.length === 0 && <p>No events registered.</p>}
        {!!events.data?.length && (
          <TargetingTable label="Event catalog" headers={['Event', 'Description', 'Linked features']}>
            {events.data.map((event) => (
              <tr key={event.key}>
                <th scope="row"><span>{event.name}</span><code className="data-key">{event.key}</code></th>
                <td>{event.description}</td>
                <td><div className="data-tags">{event.features.length ? event.features.map((key) => (
                  <span className="data-tag" key={key}>{featureNames.get(key) ?? key}</span>
                )) : '—'}</div></td>
              </tr>
            ))}
          </TargetingTable>
        )}
      </section>
    </>
  )
}
