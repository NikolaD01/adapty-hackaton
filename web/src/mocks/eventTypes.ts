import type { EventType } from '../types/events'

export const eventTypes: EventType[] = [
  {
    action_id: 3,
    key: 'regenerate_click',
    name: 'Regenerate clicked',
    description: 'User asked for a new result after the first generation',
    features: ['ai_generate'],
    created_at: '2026-11-07T18:00:00Z',
  },
]
