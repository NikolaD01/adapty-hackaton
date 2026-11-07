/**
 * Feature Signal SDK — send behavior events from the app (owner A).
 * Contract: docs/contracts/api.md (events, event-types, features). Zero runtime dependencies,
 * browser APIs only: fetch, crypto.randomUUID, setTimeout/setInterval.
 */

export type PropValue = string | number | boolean | null
export type Props = Record<string, PropValue>

export interface InitOptions {
  baseUrl: string
  appId: string
  customerUserId: string
  /** Send buffered events every N ms (default 2000). */
  flushIntervalMs?: number
  /** Send as soon as this many events are buffered (default 20). */
  maxBatch?: number
  /** Injected in tests; defaults to globalThis.fetch. */
  fetch?: typeof fetch
}

export interface FeatureInput {
  key: string
  name: string
  description: string
  plans?: string[]
}

export interface Feature extends Required<FeatureInput> {
  created_at: string
}

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

export interface QueuedEvent {
  event_id: string
  customer_user_id: string
  key: string
  occurred_at: string
  props: Props
}

export interface FlushResult {
  sent: number
  accepted: number
  duplicates: number
  unknown_keys: string[]
}

/** Contract limits (schemas/events.py): at most 20 props, strings up to 100 chars, max 500 per batch. */
export const MAX_PROPS = 20
export const MAX_PROP_STRING = 100
const MAX_REQUEST = 500

interface State {
  opts: Required<Omit<InitOptions, 'fetch'>> & { fetch: typeof fetch }
  queue: QueuedEvent[]
  timer: ReturnType<typeof setInterval> | null
  inFlight: Promise<FlushResult> | null
}

let state: State | null = null

function need(): State {
  if (!state) throw new Error('feature-signal-sdk: call init() first')
  return state
}

function url(path: string): string {
  const s = need()
  return `${s.opts.baseUrl.replace(/\/$/, '')}/v1/apps/${s.opts.appId}${path}`
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await need().opts.fetch(url(path), {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`feature-signal-sdk: ${path} failed with ${res.status}`)
  return (await res.json()) as T
}

/** Keep only values the backend accepts; free text (e.g. a prompt) never leaves the app. */
export function cleanProps(props: Record<string, unknown> = {}): Props {
  const out: Props = {}
  for (const [name, value] of Object.entries(props)) {
    if (Object.keys(out).length >= MAX_PROPS) {
      console.warn(`feature-signal-sdk: more than ${MAX_PROPS} props, dropped "${name}"`)
      continue
    }
    if (value === null || typeof value === 'boolean' || (typeof value === 'number' && Number.isFinite(value))) {
      out[name] = value
    } else if (typeof value === 'string' && value.length <= MAX_PROP_STRING) {
      out[name] = value
    } else {
      console.warn(`feature-signal-sdk: prop "${name}" dropped (send a number or a short label, never free text)`)
    }
  }
  return out
}

export function init(options: InitOptions): void {
  shutdown()
  const fetchImpl = options.fetch ?? globalThis.fetch.bind(globalThis)
  state = {
    opts: {
      baseUrl: options.baseUrl,
      appId: options.appId,
      customerUserId: options.customerUserId,
      flushIntervalMs: options.flushIntervalMs ?? 2000,
      maxBatch: options.maxBatch ?? 20,
      fetch: fetchImpl,
    },
    queue: [],
    timer: null,
    inFlight: null,
  }
  state.timer = setInterval(() => void flush().catch(() => undefined), state.opts.flushIntervalMs)
}

/** Switch the user (e.g. after login). Already buffered events keep their original user. */
export function setUser(customerUserId: string): void {
  need().opts.customerUserId = customerUserId
}

export function track(key: string, props?: Record<string, unknown>): void {
  const s = need()
  s.queue.push({
    event_id: crypto.randomUUID(),
    customer_user_id: s.opts.customerUserId,
    key,
    occurred_at: new Date().toISOString(),
    props: cleanProps(props),
  })
  if (s.queue.length >= s.opts.maxBatch) void flush().catch(() => undefined)
}

/**
 * Send everything buffered. On failure the events stay in the buffer with the same event_ids, so the
 * next flush retries them and the backend counts them once.
 */
export function flush(): Promise<FlushResult> {
  const s = need()
  if (s.inFlight) return s.inFlight
  const batch = s.queue.slice(0, MAX_REQUEST)
  if (batch.length === 0) return Promise.resolve({ sent: 0, accepted: 0, duplicates: 0, unknown_keys: [] })
  s.inFlight = postJson<Omit<FlushResult, 'sent'>>('/events', { events: batch })
    .then((r) => {
      const sentIds = new Set(batch.map((e) => e.event_id))
      s.queue = s.queue.filter((e) => !sentIds.has(e.event_id))
      if (r.unknown_keys.length) console.warn(`feature-signal-sdk: unknown event keys ${r.unknown_keys.join(', ')}`)
      return { sent: batch.length, ...r }
    })
    .finally(() => {
      s.inFlight = null
    })
  return s.inFlight
}

export function registerFeature(feature: FeatureInput): Promise<Feature> {
  return postJson<Feature>('/features', { plans: [], ...feature })
}

export function registerEventType(eventType: EventTypeInput): Promise<EventType> {
  return postJson<EventType>('/event-types', { features: [], ...eventType })
}

/** Events waiting to be sent (for debugging and tests). */
export function pending(): readonly QueuedEvent[] {
  return state ? [...state.queue] : []
}

/** Stop the timer. Buffered events are dropped unless you `await flush()` first. */
export function shutdown(): void {
  if (state?.timer) clearInterval(state.timer)
  state = null
}
