import type { OverviewMetric } from '../../types/overview'

export const overviewDates = ['8 Oct', '14 Oct', '20 Oct', '26 Oct', '1 Nov', '7 Nov']

// Values are bar heights measured from the design reference, in chart units.
export const overviewMetrics: readonly OverviewMetric[] = [
  {
    title: 'Revenue',
    total: '$14.3k',
    bars: [19, 26, 54, 35, 21, 21, 38, 26, 52, 16, 28, 30, 33, 47, 23, 30, 34, 21, 23, 20, 43, 36, 33, 53, 23, 19, 29, 20, 28, 15, 154],
    ticks: [
      { label: '$2k', height: 146 },
      { label: '$1.5k', height: 109.5 },
      { label: '$1k', height: 73 },
      { label: '$500', height: 36.5 },
      { label: '$0', height: 0 },
    ],
  },
  {
    title: 'MRR',
    total: '$6.3k',
    bars: [124, 124, 124, 123, 122, 122, 124, 123, 122, 124, 124, 129, 131, 133, 138, 138, 139, 141, 140, 143, 144, 145, 146, 145, 145, 147, 149, 149, 151, 153, 155],
    ticks: [
      { label: '$6k', height: 148 },
      { label: '$4k', height: 98.7 },
      { label: '$2k', height: 49.3 },
      { label: '$0', height: 0 },
    ],
  },
  {
    title: 'ARR',
    total: '$75.2k',
    bars: [121, 121, 121, 120, 118, 119, 121, 120, 119, 121, 121, 126, 127, 130, 134, 134, 136, 137, 137, 139, 140, 142, 142, 141, 142, 142, 144, 145, 146, 147, 151],
    ticks: [
      { label: '$80k', height: 160 },
      { label: '$60k', height: 120 },
      { label: '$40k', height: 80 },
      { label: '$20k', height: 40 },
      { label: '$0', height: 0 },
    ],
  },
  {
    title: 'ARPU',
    total: '$2.87',
    bars: [136, 74, 150, 107, 58, 86, 106, 73, 105, 44, 126, 92, 81, 107, 139, 91, 102, 97, 94, 73, 130, 87, 99, 108, 52, 61, 69, 57, 67, 107, 2],
    ticks: [
      { label: '$60', height: 160 },
      { label: '$40', height: 106.7 },
      { label: '$20', height: 53.3 },
      { label: '$0', height: 0 },
    ],
  },
]
