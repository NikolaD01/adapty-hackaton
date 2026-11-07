import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

export function DashboardLayout() {
  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="dashboard-workspace">
        <TopBar />
        <main className="dashboard-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
