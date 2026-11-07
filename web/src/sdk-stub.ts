import type { EventType, EventTypeInput } from './types/events'

interface InitOptions {
  baseUrl: string
  appId: string
  customerUserId: string
}

export function init(_options: InitOptions): void {
  // The demo has no tracking transport until the SDK is connected.
}

export async function registerEventType(_eventType: EventTypeInput): Promise<EventType> {
  throw new Error('Event registration requires the tracking SDK.')
}

export function track(_key: string, _props?: Record<string, unknown>): void {
  // The static scaffold does not send events.
}
