import { useAppQuery } from '../../shared/api'
import { QueryFeedback } from '../../shared/ui/QueryFeedback'
import type { FeatureProfile, Timeline } from '../../types/ingest'

export function DemoUserPanel({ userId }: { userId: string }) {
  const base = `/users/${encodeURIComponent(userId)}`
  const timeline = useAppQuery<Timeline>(['demo-user', userId, 'timeline'], `${base}/timeline?limit=20`)
  const profile = useAppQuery<FeatureProfile>(['demo-user', userId, 'profile'], `${base}/features`)

  return (
    <aside aria-label="User activity">
      <section className="behavioral-panel">
        <h2>Event timeline</h2>
        <QueryFeedback {...timeline} />
        {timeline.data?.items.length === 0 && <p>No events recorded.</p>}
        {timeline.data && (
          <ol>
            {timeline.data.items.map((event) => (
              <li key={event.event_id}>
                <code>{event.key}</code>
                <div><time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString()}</time></div>
              </li>
            ))}
          </ol>
        )}
      </section>
      <section className="behavioral-panel">
        <h2>Feature profile</h2>
        <QueryFeedback {...profile} />
        {profile.data?.features.length === 0 && <p>No features registered.</p>}
        {profile.data && (
          <ul>
            {profile.data.features.map((feature) => (
              <li key={feature.feature}>
                <strong>{feature.name}</strong>
                {feature.tier && <span> · {feature.tier} tier</span>}
                <dl>
                  {Object.entries(feature.values).map(([key, value]) => (
                    <div className="demo-profile-value" key={key}>
                      <dt><code>{key}</code></dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
  )
}
