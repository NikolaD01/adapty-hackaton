import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest'
import { AppProviders } from '../app/AppProviders'
import { DecisionsPage } from '../features/behavioral/DecisionsPage'
import { LookupPage } from '../features/behavioral/LookupPage'
import { freeUser, paidUser } from '../mocks/fixtures'
import { createHandlers } from '../mocks/handlers'
import { appApiUrl } from '../shared/api'

const server = setupServer(...createHandlers())
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers(...createHandlers()))
afterAll(() => server.close())

it('shows the actor, failed step and error details in the selected proposal log', async () => {
  let filter: string | null = null
  server.use(http.get(`${appApiUrl}/decisions`, ({ request }) => {
    filter = new URL(request.url).searchParams.get('proposal_id')
    return HttpResponse.json([{
      decision_id: 'dc_1', proposal_id: 'pr_1', decided_by: 'human', action: 'approve',
      at: '2026-11-08T08:00:00Z',
      steps: [
        { step: 'segments_create', ok: true, detail: { segment_id: 'seg_01' } },
        { step: 'placement_read', ok: false, detail: { code: 'placement_not_found', message: 'Check the placement ID.' } },
      ],
    }])
  }))
  render(<AppProviders><MemoryRouter initialEntries={['/dashboard/decisions?proposal_id=pr_1']}><DecisionsPage /></MemoryRouter></AppProviders>)
  expect(await screen.findByText('Human')).toBeVisible()
  expect(screen.getByText('segments_create')).toBeVisible()
  expect(screen.getByText('Failed')).toBeVisible()
  expect(screen.getByText(/placement_not_found/)).toBeVisible()
  expect(filter).toBe('pr_1')
})

it('compares the returned flows by user ID even if the API orders them differently', async () => {
  let body: unknown
  server.use(http.post(`${appApiUrl}/lookup`, async ({ request }) => {
    body = await request.json()
    return HttpResponse.json({ results: [
      { customer_user_id: paidUser, flow_name: 'Default', flow_id: 'flow-default', segment_hash: 'hash-default' },
      { customer_user_id: freeUser, flow_name: 'Targeted', flow_id: 'flow-targeted', segment_hash: 'hash-targeted' },
    ] })
  }))
  render(<AppProviders><MemoryRouter initialEntries={['/dashboard/lookup?placement=settings_upgrade']}><LookupPage /></MemoryRouter></AppProviders>)
  await userEvent.setup().click(screen.getByRole('button', { name: 'Compare flows' }))
  expect(await screen.findByText('Results for settings_upgrade')).toBeVisible()
  const cards = screen.getAllByRole('article')
  expect(within(cards[0]).getByText(freeUser)).toBeVisible()
  expect(within(cards[0]).getByText('Targeted')).toBeVisible()
  expect(within(cards[0]).getByText('flow-targeted')).toBeVisible()
  expect(within(cards[1]).getByText('hash-default')).toBeVisible()
  expect(body).toEqual({ placement: 'settings_upgrade', customer_user_ids: [freeUser, paidUser] })
})

it('requires distinct customer IDs before sending the lookup', async () => {
  render(<AppProviders><MemoryRouter><LookupPage /></MemoryRouter></AppProviders>)
  const user = userEvent.setup()
  const second = screen.getByRole('textbox', { name: 'Second customer user ID' })
  await user.clear(second)
  await user.type(second, freeUser)
  await user.click(screen.getByRole('button', { name: 'Compare flows' }))
  expect(screen.getByRole('alert')).toHaveTextContent('two different customer user IDs')
})

it('compares the targeted audience and available arms with the default audience', async () => {
  server.use(http.post(`${appApiUrl}/lookup`, () => HttpResponse.json({ results: [
    {
      customer_user_id: freeUser, segment_hash: 'targeted', audience_name: '[fs] editor', ab_test_name: 'Editor test',
      flow_name: 'Largest arm placeholder', flow_id: 'legacy-id', arms: [
        { name: 'control', weight: 20, flow_name: 'Control flow', flow_id: 'control-id' },
        { name: 'offer', weight: 80, flow_name: 'Offer flow', flow_id: 'offer-id' },
      ],
    },
    { customer_user_id: paidUser, segment_hash: 'default', audience_name: 'All Users', flow_name: 'Default flow', flow_id: 'default-id', arms: [] },
  ] })))
  render(<AppProviders><MemoryRouter><LookupPage /></MemoryRouter></AppProviders>)
  await userEvent.setup().click(screen.getByRole('button', { name: 'Compare flows' }))
  expect(await screen.findByText('[fs] editor')).toBeVisible()
  expect(screen.getByText('Editor test')).toBeVisible()
  expect(screen.getByText('control · 20%')).toBeVisible()
  expect(screen.getByText('offer · 80%')).toBeVisible()
  expect(screen.getByText('All Users')).toBeVisible()
  expect(screen.getByText('Default flow')).toBeVisible()
  expect(screen.queryByText('Largest arm placeholder')).not.toBeInTheDocument()
})
