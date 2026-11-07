import { Navigate, Route, Routes } from 'react-router-dom'
import { BehavioralLayout } from '../features/behavioral/BehavioralLayout'
import { DemoPage } from '../features/behavioral/DemoPage'
import { PlaceholderPage } from '../features/behavioral/PlaceholderPage'
import { behavioralPages } from '../features/behavioral/pages'
import { OverviewPage } from '../features/overview/OverviewPage'
import { DashboardLayout } from './layout/DashboardLayout'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<DashboardLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="dashboard" element={<BehavioralLayout />}>
          <Route index element={<Navigate to="events" replace />} />
          {behavioralPages.map(({ path, title, description }) => (
            <Route
              key={path}
              path={path}
              element={<PlaceholderPage title={title} description={description} />}
            />
          ))}
        </Route>
        <Route path="*" element={<PlaceholderPage title="Page not found" />} />
      </Route>
      <Route path="demo" element={<DemoPage />} />
    </Routes>
  )
}
