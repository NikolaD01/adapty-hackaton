import { Icon } from '../../shared/ui/Icon'

export function OverviewToolbar() {
  return (
    <div className="overview-toolbar" aria-label="Overview controls">
      <div className="toolbar-row">
        <div className="toolbar-group">
          <button className="period-control" disabled><Icon name="calendar" size={16} /> Last month | Day <Icon name="chevron-down" size={16} /></button>
          <span className="toolbar-comparison">compare to</span>
          <button disabled>No comparison <Icon name="chevron-down" size={16} /></button>
          <button disabled>Group by <Icon name="chevron-down" size={16} /></button>
        </div>
        <div className="toolbar-group">
          <button disabled>Email reports</button>
          <button disabled><Icon name="edit" size={20} /> Edit metrics</button>
        </div>
      </div>
      <div className="toolbar-row">
        <button className="add-filter" disabled>
          <span className="add-filter-icon"><Icon name="plus" size={18} /></span>
          Add filter
        </button>
        <div className="toolbar-group">
          <button aria-label="Chart display" disabled><Icon name="columns" size={22} /><Icon name="chevron-down" size={16} /></button>
          <button aria-label="Currency" disabled><Icon name="dollar" size={22} /><Icon name="chevron-down" size={16} /></button>
        </div>
      </div>
    </div>
  )
}
