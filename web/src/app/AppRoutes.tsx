import { Navigate, Route, Routes } from 'react-router-dom'
import { BehavioralLayout } from '../features/behavioral/BehavioralLayout'
import { EventsPage } from '../features/behavioral/EventsPage'
import { MetricsPage } from '../features/behavioral/MetricsPage'
import { ProposalsPage } from '../features/behavioral/ProposalsPage'
import { PendingPage } from '../features/behavioral/PendingPage'
import { PlaceholderPage } from '../features/behavioral/PlaceholderPage'
import { behavioralPages } from '../features/behavioral/pages'
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
          <Route path="proposals" element={<ProposalsPage />} />
          {behavioralPages.filter((page) => page.path !== 'events' && page.path !== 'metrics' && page.path !== 'proposals').map((page) => (
            <Route
              key={page.path}
              path={page.path}
              element={<PendingPage {...page} />}
            />
          ))}
        </Route>
        <Route path="*" element={<PlaceholderPage title="Page not found" />} />
      </Route>
      <Route path="demo" element={<DemoPage />} />
    </Routes>
  )
}
