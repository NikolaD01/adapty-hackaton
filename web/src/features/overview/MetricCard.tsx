import { Icon } from '../../shared/ui/Icon'
import type { OverviewMetric } from '../../types/overview'
import { MetricChart } from './MetricChart'

export function MetricCard({ metric }: { metric: OverviewMetric }) {
  return (
    <article className="metric-card">
      <div className="metric-label">
        <h3>{metric.title} <Icon name="help" size={12} /></h3>
        <p>{metric.total}</p>
      </div>
      <MetricChart metric={metric} />
      <span className="metric-options"><Icon name="chevron-down" size={16} /></span>
    </article>
  )
}
