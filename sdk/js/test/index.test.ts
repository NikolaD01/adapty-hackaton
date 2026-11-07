import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanProps, flush, init, pending, registerEventType, registerFeature, shutdown, track } from '../src/index'

const APP = 'c6c7bdd1-1010-4343-8b29-837a77793cab'

function okFetch(body: unknown = { accepted: 1, duplicates: 0, unknown_keys: [] }) {
  return vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(body), { status: 200 }))
}

function sentEvents(fetchMock: ReturnType<typeof okFetch>, call = 0) {
  return JSON.parse(String(fetchMock.mock.calls[call][1]?.body)).events
}

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  shutdown()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('track and flush', () => {
  it('posts events in the contract shape to the app events endpoint', async () => {
    const f = okFetch()
    init({ baseUrl: 'http://api/', appId: APP, customerUserId: 'u_42', fetch: f })
    track('generate_click', { tokens_used: 40, tokens_left: 0, with_upload: true })
    await flush()
    expect(f.mock.calls[0][0]).toBe(`http://api/v1/apps/${APP}/events`)
    const [e] = sentEvents(f)
    expect(e.key).toBe('generate_click')
    expect(e.customer_user_id).toBe('u_42')
    expect(e.props).toEqual({ tokens_used: 40, tokens_left: 0, with_upload: true })
    expect(e.event_id).toMatch(/^[0-9a-f-]{36}$/)
    expect(new Date(e.occurred_at).toISOString()).toBe(e.occurred_at)
    expect(pending()).toHaveLength(0)
  })

  it('flushes on its own every 2 seconds', async () => {
    const f = okFetch()
    init({ baseUrl: 'http://api', appId: APP, customerUserId: 'u', fetch: f })
    track('generate_click')
    expect(f).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(2000)
    expect(f).toHaveBeenCalledTimes(1)
  })

  it('flushes as soon as 20 events are buffered', async () => {
    const f = okFetch({ accepted: 20, duplicates: 0, unknown_keys: [] })
    init({ baseUrl: 'http://api', appId: APP, customerUserId: 'u', fetch: f })
    for (let i = 0; i < 20; i++) track('generate_click', { i })
    await vi.advanceTimersByTimeAsync(0)
    expect(f).toHaveBeenCalledTimes(1)
    expect(sentEvents(f)).toHaveLength(20)
  })

  it('retries a failed batch with the same event ids', async () => {
    const f = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('offline'))
      .mockResolvedValueOnce(new Response(JSON.stringify({ accepted: 1, duplicates: 0, unknown_keys: [] })))
    init({ baseUrl: 'http://api', appId: APP, customerUserId: 'u', fetch: f })
    track('generate_click')
    await expect(flush()).rejects.toThrow('offline')
    const id = pending()[0].event_id
    await flush()
    expect(JSON.parse(String(f.mock.calls[1][1].body)).events[0].event_id).toBe(id)
    expect(pending()).toHaveLength(0)
  })

  it('keeps events when the server answers 500', async () => {
    const f = vi.fn(async () => new Response('boom', { status: 500 }))
    init({ baseUrl: 'http://api', appId: APP, customerUserId: 'u', fetch: f })
    track('generate_click')
    await expect(flush()).rejects.toThrow('500')
    expect(pending()).toHaveLength(1)
  })

  it('does not lose events tracked while a flush is in flight', async () => {
    let release!: (r: Response) => void
    const f = vi.fn(() => new Promise<Response>((r) => (release = r)))
    init({ baseUrl: 'http://api', appId: APP, customerUserId: 'u', fetch: f })
    track('generate_click', { n: 1 })
    const p = flush()
    track('generate_click', { n: 2 })
    release(new Response(JSON.stringify({ accepted: 1, duplicates: 0, unknown_keys: [] })))
    await p
    expect(pending().map((e) => e.props.n)).toEqual([2])
  })
})

describe('props', () => {
  it('drops free text, objects and NaN, keeps numbers, bools, null and short labels', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const out = cleanProps({ prompt: 'x'.repeat(101), tokens_left: 0, ok: false, plan: 'free', nested: { a: 1 }, bad: NaN, none: null })
    expect(out).toEqual({ tokens_left: 0, ok: false, plan: 'free', none: null })
    expect(warn).toHaveBeenCalledTimes(3)
  })

  it('keeps at most 20 props', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const many = Object.fromEntries(Array.from({ length: 25 }, (_, i) => [`p${i}`, i]))
    expect(Object.keys(cleanProps(many))).toHaveLength(20)
  })
})

describe('catalog', () => {
  it('registers features and event types', async () => {
    const f = vi.fn(async (_u: string, i?: RequestInit) => new Response(String(i?.body), { status: 200 }))
    init({ baseUrl: 'http://api', appId: APP, customerUserId: 'u', fetch: f })
    await registerFeature({ key: 'ai_generate', name: 'AI generation', description: 'd' })
    const et = await registerEventType({ key: 'generate_click', name: 'Generate', description: 'd', features: ['ai_generate'] })
    expect(f.mock.calls[0][0]).toBe(`http://api/v1/apps/${APP}/features`)
    expect(JSON.parse(String(f.mock.calls[0][1]?.body)).plans).toEqual([])
    expect(f.mock.calls[1][0]).toBe(`http://api/v1/apps/${APP}/event-types`)
    expect(et.features).toEqual(['ai_generate'])
  })

  it('throws a clear error before init', () => {
    expect(() => track('x')).toThrow('call init() first')
  })
})
