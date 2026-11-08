export const behavioralPages = [
  { path: 'events', title: 'Events', description: 'The event catalog will list the actions tracked by your app.' },
  { path: 'metrics', title: 'Metrics', description: 'Metrics turn tracked events into values you can use in rules.' },
  { path: 'insights', title: 'Insights', description: 'Review which metrics relate to purchase outcomes.', endpoint: '/insights/latest' },
  { path: 'proposals', title: 'Proposals', description: 'Review proposed changes to paywall targeting.', endpoint: '/proposals' },
  { path: 'decisions', title: 'Decisions', description: 'See decisions and the actions taken for each one.', endpoint: '/decisions' },
  { path: 'lookup', title: 'Lookup', description: 'Compare the flow served to two users at the same placement.' },
] as const
