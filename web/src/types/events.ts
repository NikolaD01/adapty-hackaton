export interface EventTypeInput {
  key: string
  name: string
  description: string
  features?: string[]
}

export interface EventType extends EventTypeInput {
  action_id: number
  features: string[]
  created_at: string
}
