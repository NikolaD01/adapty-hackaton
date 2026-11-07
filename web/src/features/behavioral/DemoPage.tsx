import { Link } from 'react-router-dom'
import { PlaceholderPage } from './PlaceholderPage'

export function DemoPage() {
  return (
    <main className="demo-page">
      <PlaceholderPage title="Lumen demo" description="Preview of the app used to demonstrate event tracking." />
      <Link to="/dashboard/events">Back to Events</Link>
    </main>
  )
}
