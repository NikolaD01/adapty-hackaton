import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { PreviewNotice } from '../../shared/ui/PreviewNotice'
import { behavioralPages } from './pages'

export function BehavioralLayout() {
  const { pathname } = useLocation()
  return (
    <section className="behavioral-section">
      <header className="targeting-navigation">
        <p className="behavioral-section-name">Behavioral Targeting</p>
        <nav className="feature-navigation" aria-label="Behavioral Targeting">
          {behavioralPages.map(({ path, title }) => (
            <NavLink key={path} to={path}>{title}</NavLink>
          ))}
          <Link className="demo-link" to="/demo">Lumen demo</Link>
        </nav>
      </header>
      <PreviewNotice />
      <div className="targeting-view" key={pathname}>
        <Outlet />
      </div>
    </section>
  )
}
