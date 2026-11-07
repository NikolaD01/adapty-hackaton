import type { OverviewMetric } from '../../types/overview'
import { overviewDates } from './overviewMetrics'

const plotWidth = 493
const plotHeight = 172

export function MetricChart({ metric }: { metric: OverviewMetric }) {
  const barStep = plotWidth / metric.bars.length
  const barWidth = barStep * 0.8

  return (
    <div className="metric-chart" role="img" aria-label={`${metric.title} from 8 October to 7 November`}>
      <div className="metric-chart-ticks" aria-hidden="true">
        {metric.ticks.map(({ label, height }) => (
          <span key={label} style={{ bottom: `${height / plotHeight * 100}%` }}>{label}</span>
        ))}
      </div>
      <svg
        className="metric-chart-plot"
        viewBox={`0 0 ${plotWidth} ${plotHeight}`}
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {metric.ticks.map(({ label, height }) => {
          const y = plotHeight - height
          return <line key={label} x1={0} x2={plotWidth} y1={y} y2={y} />
        })}
        {metric.bars.map((height, index) => (
          <rect
            key={index}
            x={index * barStep + (barStep - barWidth) / 2}
            y={plotHeight - height}
            width={barWidth}
            height={height}
            rx="1.4"
          />
        ))}
      </svg>
      <div className="metric-chart-dates" aria-hidden="true">
        {overviewDates.map((label) => <span key={label}>{label}</span>)}
      </div>
    </div>
  )
}
