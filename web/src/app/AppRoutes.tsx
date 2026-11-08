import { Navigate, Route, Routes } from 'react-router-dom'
import { BehavioralLayout } from '../features/behavioral/BehavioralLayout'
import { DecisionsPage } from '../features/behavioral/DecisionsPage'
import { EventsPage } from '../features/behavioral/EventsPage'
import { InsightsPage } from '../features/behavioral/InsightsPage'
import { LookupPage } from '../features/behavioral/LookupPage'
import { MetricsPage } from '../features/behavioral/MetricsPage'
import { PlaceholderPage } from '../features/behavioral/PlaceholderPage'
import { ProposalsPage } from '../features/behavioral/ProposalsPage'
import { DemoPage } from '../features/demo/DemoPage'
import { OverviewPage } from '../features/overview/OverviewPage'
import { DashboardLayout } from './layout/DashboardLayout'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<DashboardLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="dashboard" element={<BehavioralLayout />}>
          <Route index element={<Navigate to="events" replace />} />
          <Route path="events" element={<EventsPage />} />
          <Route path="metrics" element={<MetricsPage />} />
          <Route path="insights" element={<InsightsPage />} />
          <Route path="proposals" element={<ProposalsPage />} />
          <Route path="decisions" element={<DecisionsPage />} />
          <Route path="lookup" element={<LookupPage />} />
        </Route>
        <Route path="*" element={<PlaceholderPage title="Page not found" />} />
      </Route>
      <Route path="demo" element={<DemoPage />} />
    </Routes>
  )
}
