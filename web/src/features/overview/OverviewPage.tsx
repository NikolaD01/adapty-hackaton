import { Icon } from '../../shared/ui/Icon'
import { MetricCard } from './MetricCard'
import { OverviewToolbar } from './OverviewToolbar'
import { overviewMetrics } from './overviewMetrics'
import './overview.css'

export function OverviewPage() {
  return (
    <>
      <div className="overview-heading">
        <h1>Overview</h1>
        <span className="overview-docs"><Icon name="external" size={16} />Read the docs</span>
      </div>
      <OverviewToolbar />
      <section className="money-section" aria-labelledby="money-title">
        <h2 id="money-title">Money</h2>
        <div className="metrics-grid">
          {overviewMetrics.map((metric) => <MetricCard key={metric.title} metric={metric} />)}
        </div>
      </section>
    </>
  )
}
