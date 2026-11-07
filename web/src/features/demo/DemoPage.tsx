import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PlaceholderPage } from '../behavioral/PlaceholderPage'
import { demoActions, demoUsers } from './demoActions'
import { DemoUserPanel } from './DemoUserPanel'
import { useDemoTracking } from './useDemoTracking'

export function DemoPage() {
  const [userIndex, setUserIndex] = useState(0)
  const user = demoUsers[userIndex]
  const tracking = useDemoTracking(user)

  return (
    <main className="demo-page">
      <PlaceholderPage title="Lumen demo" description="Simulate a photo-editing session for a seeded user." />
      <div className="demo-grid">
        <section className="behavioral-panel">
          <h2>Photo editor</h2>
          <label className="demo-user">
            Demo user
            <select
              value={userIndex}
              disabled={tracking.isPending || tracking.isError}
              onChange={(event) => setUserIndex(Number(event.target.value))}
            >
              {demoUsers.map((demoUser, index) => (
                <option key={demoUser.id} value={index}>{demoUser.label}</option>
              ))}
            </select>
          </label>
          <p><code>{user.id}</code></p>
          <div className="demo-actions">
            {demoActions.map(({ key, label }) => (
              <button key={key} disabled={tracking.isPending || tracking.isError} onClick={() => tracking.mutate(key)}>
                {label}
              </button>
            ))}
          </div>
          {!user.premium && <p>Full-resolution export is Pro only.</p>}
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
