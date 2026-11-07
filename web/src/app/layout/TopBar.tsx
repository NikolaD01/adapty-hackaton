import { Icon } from '../../shared/ui/Icon'

export function TopBar() {
  return (
    <header className="top-bar">
      <div className="team"><span className="team-avatar">T</span>Team 5</div>
      <div className="top-bar-actions" aria-label="Account controls">
        <span className="notification" aria-label="5 notifications">
          <Icon name="bell" size={22} />
          <span className="notification-count" aria-hidden="true">5</span>
        </span>
        <span>Help</span>
        <span>App settings</span>
        <span>Account</span>
      </div>
    </header>
  )
}
