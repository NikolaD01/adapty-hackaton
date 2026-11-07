import type { IconName } from '../../shared/ui/Icon'

export const sidebarItems = [
  { label: 'Analytics', icon: 'chart' },
  { label: 'Profiles & Segments', icon: 'users' },
  { label: 'Products', icon: 'product' },
  { label: 'Flows & Paywalls', icon: 'flow' },
  { label: 'Placements', icon: 'pin' },
  { label: 'Retention Messaging', icon: 'retention' },
  { label: 'A/B tests', icon: 'ab' },
] satisfies ReadonlyArray<{ label: string; icon: IconName }>
