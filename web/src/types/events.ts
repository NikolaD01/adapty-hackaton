export interface EventTypeInput {
  key: string
  name: string
  description: string
  family?: string | null
}

export interface EventType extends EventTypeInput {
  action_id: number
  created_at: string
}
