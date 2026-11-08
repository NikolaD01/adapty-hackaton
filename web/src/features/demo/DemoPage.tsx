import type { Feature } from 'feature-signal-sdk'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAppQuery } from '../../shared/api'
import { PreviewNotice } from '../../shared/ui/PreviewNotice'
import { RequestError } from '../../shared/ui/QueryFeedback'
import { PlaceholderPage } from '../behavioral/PlaceholderPage'
import { demoActions, demoUsers } from './demoActions'
import { DemoUserPanel } from './DemoUserPanel'
import { useDemoTracking } from './useDemoTracking'

export function DemoPage() {
  const [userIndex, setUserIndex] = useState(0)
  const user = demoUsers[userIndex]
  const catalog = useAppQuery<Feature[]>(['features'], '/features')
  const plans = catalog.data?.find(({ key }) => key === 'hd_export')?.plans.filter(Boolean) ?? []
  const canExportHd = plans.length ? user.accessLevel !== null && plans.includes(user.accessLevel) : undefined
  const tracking = useDemoTracking(user, canExportHd)

  return (
    <main className="demo-page">
      <PlaceholderPage title="Lumen demo" description="Simulate a photo-editing session for a seeded user." />
      <PreviewNotice />
      <div className="demo-grid">
        <section className="behavioral-panel">
          <h2>Photo editor</h2>
          <label className="demo-user">
            Demo user
            <select
              value={userIndex}
              disabled={tracking.isPending || tracking.isError}
              onChange={(event) => { tracking.reset(); setUserIndex(Number(event.target.value)) }}
            >
              {demoUsers.map((demoUser, index) => (
                <option key={demoUser.id} value={index}>{demoUser.label}</option>
              ))}
            </select>
          </label>
          <p><code>{user.id}</code></p>
          {tracking.editsLeft !== null && <p>Free AI edits left <strong>{tracking.editsLeft}</strong></p>}
          <div className="demo-actions">
            {demoActions.map(({ key, label }) => (
              <button key={key}
                disabled={tracking.isPending || tracking.isError
                  || (key === 'export_hd_attempt' && canExportHd === undefined)
                  || (key === 'ai_enhance' && tracking.editsLeft === 0)}
                onClick={() => tracking.mutate(key)}>{label}</button>
            ))}
          </div>
          {catalog.isPending && <p role="status">Checking HD export access…</p>}
          <RequestError error={catalog.error} />
          {catalog.isSuccess && canExportHd === undefined && <p>HD export needs an eligible plan in the catalog.</p>}
          {canExportHd === false && (
            <p>Full-resolution export requires {plans.map((plan) => plan.charAt(0).toUpperCase() + plan.slice(1)).join(' or ')}.</p>
          )}
          {tracking.isPending && <p role="status">Sending event and refreshing activity…</p>}
          {tracking.isSuccess && <p role="status">Activity refreshed.</p>}
          {tracking.isError && (
            <>
              <p role="alert">{tracking.error.message}</p>
              <button onClick={() => tracking.mutate(null)}>Retry sync</button>
            </>
          )}
        </section>
        <DemoUserPanel userId={user.id} />
      </div>
      <Link to="/dashboard/events">Back to Events</Link>
    </main>
  )
}
