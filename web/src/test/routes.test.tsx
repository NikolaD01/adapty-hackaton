import { render, screen, waitForElementToBeRemoved, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { QueuedEvent } from 'feature-signal-sdk'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { AppProviders } from '../app/AppProviders'
import { AppRoutes } from '../app/AppRoutes'
import { demoUsers } from '../features/demo/demoActions'
import { mockFeatures } from '../mocks/fixtures'
import { server } from '../mocks/server'
import { appApiUrl } from '../shared/api'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(mockLiveReads)
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function mockLiveReads() {
  server.use(
    http.get(`${appApiUrl}/features`, () => HttpResponse.json(mockFeatures)),
    http.get(`${appApiUrl}/event-types`, () => HttpResponse.json([])),
    http.get(`${appApiUrl}/rules`, () => HttpResponse.json([])),
    http.get(`${appApiUrl}/values`, () => HttpResponse.json({ items: [], next_cursor: null })),
    http.get(`${appApiUrl}/users/:userId/timeline`, () => HttpResponse.json({ items: [] })),
    http.get(`${appApiUrl}/users/:userId/features`, () => HttpResponse.json({ features: [] })),
  )
}

function renderRoute(path: string) {
  return render(
    <AppProviders>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  )
}

describe('dashboard scaffold', () => {
  it('renders the four reference charts and links to Behavioral Targeting', async () => {
    renderRoute('/')
    const user = userEvent.setup()

    expect(screen.getByRole('heading', { level: 1, name: 'Overview' })).toBeInTheDocument()
    for (const title of ['Revenue', 'MRR', 'ARR', 'ARPU']) {
      expect(screen.getByRole('heading', { name: title })).toBeInTheDocument()
      expect(screen.getByRole('img', { name: new RegExp(`^${title} from`) })).toBeInTheDocument()
    }

    const sidebar = within(screen.getByRole('navigation', { name: 'Dashboard' }))
    expect(sidebar.getAllByRole('link')).toHaveLength(2)
    await user.click(sidebar.getByText('Analytics'))
    expect(screen.getByRole('heading', { name: 'Overview' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit metrics' })).toBeDisabled()

    await user.click(sidebar.getByRole('link', { name: 'Behavioral Targeting' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Events' })).toBeInTheDocument()
  })

  it.each(['Overview', 'Adapty'])('returns from Events via the %s link', async (linkName) => {
    renderRoute('/dashboard/events')
    const user = userEvent.setup()

    await user.click(screen.getByRole('link', { name: linkName }))

    expect(screen.getByRole('heading', { level: 1, name: 'Overview' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page')
  })

  it.each([
    ['/dashboard/events', 'Events'],
    ['/dashboard/metrics', 'Metrics'],
    ['/dashboard/insights', 'Insights'],
    ['/dashboard/proposals', 'Proposals'],
    ['/dashboard/decisions', 'Decisions'],
    ['/dashboard/lookup', 'Lookup'],
    ['/demo', 'Lumen demo'],
    ['/dashboard', 'Events'],
    ['/unknown', 'Page not found'],
  ])('renders %s as %s', (path, heading) => {
    renderRoute(path)
    expect(screen.getByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
  })

  it('omits unavailable read placeholders and reports unavailable run actions', async () => {
    server.use(
      http.get(`${appApiUrl}/insights/latest`, () => new HttpResponse(null, { status: 501 })),
      http.post(`${appApiUrl}/insights:run`, () => new HttpResponse(null, { status: 501 })),
    )
    renderRoute('/dashboard/insights')
    await waitForElementToBeRemoved(() => screen.queryByText('Loading…'))
    expect(screen.queryByText('Coming soon')).not.toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Run insights' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('This action is unavailable.')
  })

  it('flushes a blocked HD export before refreshing both demo panels', async () => {
    const userId = demoUsers[0].id
    const history: QueuedEvent[] = []
    const user = userEvent.setup()
    server.use(
      http.post(`${appApiUrl}/events`, async ({ request }) => {
        const { events } = await request.json() as { events: QueuedEvent[] }
        history.push(...events)
        return HttpResponse.json({ accepted: events.length, duplicates: 0, unknown_keys: [] })
      }),
      http.get(`${appApiUrl}/users/${userId}/timeline`, () => HttpResponse.json({ items: history })),
      http.get(`${appApiUrl}/users/${userId}/features`, () => HttpResponse.json({
        features: [{
          feature: 'hd_export',
          name: 'HD export',
          values: { attempts: history.length ? 1 : 0 },
          tier: null,
        }],
      })),
    )

    renderRoute('/demo')
    await screen.findByText('No events recorded.')
    await screen.findByText('0')
    expect(await screen.findByText('Full-resolution export requires Premium.')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Export in full resolution' }))

    expect(await screen.findByText('pt_track_hd_export_blocked')).toBeInTheDocument()
    expect(await screen.findByText('HD export')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(history.map((event) => [event.customer_user_id, event.key])).toEqual([
      [userId, 'export_hd_attempt'],
      [userId, 'pt_track_hd_export_blocked'],
    ])
    expect(await screen.findByText('Activity refreshed.')).toBeInTheDocument()
  })

  it('tracks an HD attempt without a blocked event when the selected user has the plan', async () => {
    const history: QueuedEvent[] = []
    server.use(http.post(`${appApiUrl}/events`, async ({ request }) => {
      const { events } = await request.json() as { events: QueuedEvent[] }
      history.push(...events)
      return HttpResponse.json({ accepted: events.length, duplicates: 0, unknown_keys: [] })
    }))
    renderRoute('/demo')
    const user = userEvent.setup()
    await screen.findByText('Full-resolution export requires Premium.')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Demo user' }), '1')
    await user.click(screen.getByRole('button', { name: 'Export in full resolution' }))
    expect(await screen.findByText('Activity refreshed.')).toBeVisible()
    expect(history.map((event) => [event.customer_user_id, event.key])).toEqual([
      [demoUsers[1].id, 'export_hd_attempt'],
    ])
  })
})
