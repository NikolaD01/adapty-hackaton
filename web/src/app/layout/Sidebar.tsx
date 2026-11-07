import { Link, NavLink, useMatch } from 'react-router-dom'
import { Icon } from '../../shared/ui/Icon'
import { GettingStarted } from './GettingStarted'
import { sidebarItems } from './sidebarItems'

export function Sidebar() {
  const behavioral = useMatch('/dashboard/*')

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <Link className="adapty-brand" to="/" aria-label="Adapty">
          <svg aria-hidden="true" viewBox="0 0 22 24">
            <path d="M10 4a10 10 0 0 0 0 20ZM12 24A10 10 0 0 0 22 14V0a10 10 0 0 0-10 10Z" fill="currentColor" />
          </svg>
          <span className="sidebar-label">adapty</span>
        </Link>
        <Icon name="chevron-down" size={12} />
        <span className="sidebar-collapse"><Icon name="chevrons-left" size={14} /></span>
      </div>
      <div className="sidebar-content">
        <nav aria-label="Dashboard">
          <ul className="sidebar-menu">
            <li>
              <NavLink
                className={({ isActive }) => isActive ? 'sidebar-item sidebar-item-current' : 'sidebar-item'}
                end
                title="Overview"
                to="/"
              >
                <Icon name="gauge" size={20} />
                <span className="sidebar-label">Overview</span>
              </NavLink>
            </li>
            {sidebarItems.map(({ label, icon }) => (
              <li key={label}>
                <span className="sidebar-item" aria-disabled="true" title={label}>
                  <Icon name={icon} size={20} />
                  <span className="sidebar-label">{label}</span>
                </span>
              </li>
            ))}
            <li>
              <Link
                className={behavioral ? 'sidebar-item feature-link sidebar-item-current' : 'sidebar-item feature-link'}
                aria-current={behavioral ? 'page' : undefined}
                title="Behavioral Targeting"
                to="/dashboard/events"
              >
                <Icon name="activity" size={20} />
                <span className="sidebar-label">Behavioral Targeting</span>
                <span className="feature-short-label" aria-hidden="true">Targeting</span>
              </Link>
            </li>
          </ul>
        </nav>
        <GettingStarted />
        <div className="sidebar-footer" aria-disabled="true">
          <Icon name="demo" size={18} />
          Explore Demo
        </div>
      </div>
    </aside>
  )
}
