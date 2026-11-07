import type { EventType, Feature } from 'feature-signal-sdk'
import { useAppQuery } from '../../shared/api'
import { QueryFeedback } from '../../shared/ui/QueryFeedback'
import { PlaceholderPage } from './PlaceholderPage'

export function EventsPage() {
  const features = useAppQuery<Feature[]>(['features'], '/features')
  const events = useAppQuery<EventType[]>(['event-types'], '/event-types')

  return (
    <>
      <PlaceholderPage title="Events" description="Features and actions registered by your app." />
      <section className="behavioral-panel">
        <h2>Features</h2>
        <QueryFeedback {...features} />
        {features.data?.length === 0 && <p>No features registered.</p>}
        {features.data && (
          <ul>
            {features.data.map((feature) => (
              <li key={feature.key}>
                <strong>{feature.name}</strong> <code>{feature.key}</code>
                <div>{feature.description}</div>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="behavioral-panel">
        <h2>Event catalog</h2>
        <QueryFeedback {...events} />
        {events.data?.length === 0 && <p>No events registered.</p>}
        {events.data && (
          <ul>
            {events.data.map((event) => (
              <li key={event.key}>
                <strong>{event.name}</strong> <code>{event.key}</code>
                <div>{event.description}</div>
                {event.features.length > 0 && <small>Features {event.features.join(', ')}</small>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
