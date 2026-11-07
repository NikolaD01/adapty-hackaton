export interface OverviewMetric {
  title: string
  total: string
  bars: readonly number[]
  ticks: readonly { label: string; height: number }[]
}
