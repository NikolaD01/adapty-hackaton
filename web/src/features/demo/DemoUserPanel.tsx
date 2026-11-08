import { useAppQuery } from '../../shared/api'
import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Icon } from '../../shared/ui/Icon'
import { QueryFeedback } from '../../shared/ui/QueryFeedback'
import type { FeatureProfile, Timeline } from '../../types/ingest'
import { blockedExport } from './demoActions'

const eventNames: Record<string, string> = {
  photo_import: 'Photo imported',
  bg_remove: 'Background removed',
  ai_enhance: 'AI enhance',
  export: 'Export requested',
  export_hd_attempt: 'HD export attempted',
  [blockedExport]: 'HD export blocked',
}

const timeFormat = new Intl.DateTimeFormat(undefined, { timeStyle: 'medium' })

export function useDemoProfile(userId: string) {
  return useAppQuery<FeatureProfile>(['demo-user', userId, 'profile'], `/users/${encodeURIComponent(userId)}/features`)
}

export function DemoUserPanel({ userId, eventIds, syncing }: {
  userId: string
  eventIds: readonly string[]
  syncing: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const technicalId = useId()
  const profileId = useId()
  const scroll = useRef<HTMLDivElement>(null)
  const base = `/users/${encodeURIComponent(userId)}`
  const timeline = useAppQuery<Timeline>(['demo-user', userId, 'timeline'], `${base}/timeline?limit=20`)
  const profile = useDemoProfile(userId)
  const features = profile.data?.features ?? []
  const newEvents = new Set(eventIds)
  const events = [...timeline.data?.items ?? []].sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at))
  const visibleNewEvents = events.filter(({ event_id }) => newEvents.has(event_id)).length
  const metrics = [
    { label: 'AI edits in the last 7 days', value: features.find(({ feature }) => feature === 'ai_enhance')?.values.ai_enhance_uses_7d },
    { label: 'HD export activity in the last 7 days', value: features.find(({ feature }) => feature === 'hd_export')?.values.hd_export_uses_7d },
  ]

  useEffect(() => {
    if (visibleNewEvents && scroll.current) scroll.current.scrollTop = 0
  }, [eventIds, visibleNewEvents])

  return (
    <aside className="demo-activity" aria-label="User activity">
      <section>
        <h2>Event timeline</h2>
        <QueryFeedback {...timeline} />
        {timeline.data?.items.length === 0 && <p>No events recorded.</p>}
        {events.length > 0 && (
          <div className="demo-timeline-scroll" ref={scroll} tabIndex={0} role="region" aria-label="Recent events">
            <table className="demo-timeline">
              <thead><tr><th scope="col">Event</th><th scope="col">Time</th></tr></thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.event_id} className={newEvents.has(event.event_id) ? 'demo-event-new' : undefined}>
                    <td>{eventNames[event.key] ?? event.key.replaceAll('_', ' ')}</td>
                    <td><time dateTime={event.occurred_at}>{timeFormat.format(new Date(event.occurred_at))}</time></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="demo-event-status" role="status">
          {syncing ? 'Sending events…' : visibleNewEvents > 0
            ? `Last action recorded ${visibleNewEvents} ${visibleNewEvents === 1 ? 'event' : 'events'}.` : ''}
        </p>
      </section>
      <section aria-labelledby={profileId}>
        <h2 id={profileId}>Feature profile</h2>
        <QueryFeedback {...profile} />
        {profile.data?.features.length === 0 && <p>No features registered.</p>}
        {features.length > 0 && (
          <dl>{metrics.map(({ label, value }) => (
            <div className="demo-profile-value" key={label}>
              <dt>{label}</dt>
              <dd key={value} className="demo-metric">{value ?? '—'}</dd>
            </div>
          ))}</dl>
        )}
      </section>
      <section className="demo-technical">
        <button type="button" aria-expanded={expanded} aria-controls={technicalId}
          onClick={() => setExpanded((current) => !current)}>
          <Icon name="chevron-down" size={16} />
          Technical details
        </button>
        <div id={technicalId} className="demo-technical-panel" data-expanded={expanded} aria-hidden={!expanded}>
          <div className="demo-technical-clip">
            <div className="demo-technical-content">
              <p>Profile <code>{userId}</code></p>
              {events.length > 0 && <p>Recent event keys <code>{[...new Set(events.map(({ key }) => key))].join(', ')}</code></p>}
              {features.map(({ feature, name, tier, values }) => (
                <div key={feature}>
                  <h3>{name}{tier && ` · ${tier} tier`}</h3>
                  <dl>{Object.entries(values).map(([key, value]) => (
                    <div className="demo-profile-value" key={key}><dt><code>{key}</code></dt><dd>{value}</dd></div>
                  ))}</dl>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
      <Link to="/dashboard/insights">View Insights →</Link>
    </aside>
  )
}
