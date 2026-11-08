import type { Feature } from 'feature-signal-sdk'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAppQuery } from '../../shared/api'
import { PreviewNotice } from '../../shared/ui/PreviewNotice'
import { RequestError } from '../../shared/ui/QueryFeedback'
import { Select } from '../../shared/ui/Select'
import { demoActions, demoUsers } from './demoActions'
import { DemoUserPanel } from './DemoUserPanel'
import { useDemoTracking } from './useDemoTracking'
import './demo.css'

export function DemoPage() {
  const [userIndex, setUserIndex] = useState(0)
  const user = demoUsers[userIndex]
  const catalog = useAppQuery<Feature[]>(['features'], '/features')
  const plans = catalog.data?.find(({ key }) => key === 'hd_export')?.plans.filter(Boolean) ?? []
  const canExportHd = plans.length ? user.accessLevel !== null && plans.includes(user.accessLevel) : undefined
  const tracking = useDemoTracking(user, canExportHd)
  const busy = tracking.isPending || tracking.isError
  const [tools, exports] = [demoActions.slice(0, 3), demoActions.slice(3)]

  return (
    <main className="demo-page">
      <header className="demo-heading">
        <div><h1>Lumen demo</h1><span>Demo data</span></div>
        <p>Try the photo tools and watch the events appear.</p>
      </header>
      <PreviewNotice />
      <div className="demo-workbench">
        <section className="demo-editor" aria-labelledby="demo-editor-title">
          <header className="demo-editor-header">
            <h2 id="demo-editor-title">Photo editor</h2>
            <Select label="Demo user" value={userIndex}
              disabled={busy}
              onChange={(index) => { tracking.reset(); setUserIndex(index) }}
              options={demoUsers.map(({ label }, index) => ({ value: index, label }))} />
            {tracking.editsLeft !== null && <span className="demo-quota">{tracking.editsLeft} AI edits left</span>}
          </header>
          <div className="demo-canvas">
            <img src={`${import.meta.env.BASE_URL}lumen-bicycle.jpg`} alt="Orange bicycle leaning against a weathered wall" />
          </div>
          <div className="targeting-actions demo-tools">
            {tools.map(({ key, label }) => (
              <button key={key} type="button" disabled={busy || (key === 'ai_enhance' && tracking.editsLeft === 0)}
                onClick={() => tracking.mutate(key)}>{label}</button>
            ))}
          </div>
          <div className="demo-export">
            <div className="targeting-actions">
              {exports.map(({ key, label }) => (
                <button key={key} type="button" className={key === 'export_hd_attempt' ? 'primary-action' : undefined}
                  disabled={busy || (key === 'export_hd_attempt' && canExportHd === undefined)}
                  onClick={() => tracking.mutate(key)}>{label}</button>
              ))}
            </div>
            {catalog.isPending && <p role="status">Checking HD export access…</p>}
            <RequestError error={catalog.error} />
            {catalog.isSuccess && canExportHd === undefined && <p>HD export needs an eligible plan in the catalog.</p>}
            {canExportHd === false && (
              <p className="demo-plan-note">Full-resolution export requires {plans.map((plan) => plan.charAt(0).toUpperCase() + plan.slice(1)).join(' or ')}.</p>
            )}
          </div>
          {tracking.isError && <div className="targeting-actions">
            <p role="alert">{tracking.error.message}</p>
            <button type="button" onClick={() => tracking.mutate(null)}>Retry sync</button>
          </div>}
        </section>
        <DemoUserPanel userId={user.id} eventIds={tracking.data ?? []} syncing={tracking.isPending} />
      </div>
      <Link to="/dashboard/events">Back to Events</Link>
    </main>
  )
}
