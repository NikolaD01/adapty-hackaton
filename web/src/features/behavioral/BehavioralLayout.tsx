import { Link, NavLink, Outlet } from 'react-router-dom'
import { behavioralPages } from './pages'

export function BehavioralLayout() {
  return (
    <section className="behavioral-section">
      <p className="behavioral-section-name">Behavioral Targeting</p>
      <nav className="feature-navigation" aria-label="Behavioral Targeting">
        {behavioralPages.map(({ path, title }) => (
          <NavLink key={path} to={path}>{title}</NavLink>
        ))}
        <Link className="demo-link" to="/demo">Lumen demo</Link>
      </nav>
      <Outlet />
    </section>
  )
}
