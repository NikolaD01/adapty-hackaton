import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest'
import { AppProviders } from '../app/AppProviders'
import { InsightsPage } from '../features/behavioral/InsightsPage'
import { MetricsPage } from '../features/behavioral/MetricsPage'
import { mockInsight, mockProposal, mockSuggestions } from '../mocks/fixtures'
import { createHandlers } from '../mocks/handlers'
import { appApiUrl } from '../shared/api'

const server = setupServer(...createHandlers())
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers(...createHandlers()))
afterAll(() => server.close())

it('accepts the exact suggested rule and displays it in Metrics', async () => {
  let body: unknown
  server.use(http.post(`${appApiUrl}/rules`, async ({ request }) => {
    body = await request.clone().json()
    return undefined
  }))
  render(<AppProviders><MetricsPage /></AppProviders>)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Suggest with AI' }))
  expect(await screen.findByText(mockSuggestions.suggestions[0].rationale)).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Accept' }))
  const list = screen.getByRole('heading', { name: 'Rules' }).parentElement!
  expect(await within(list).findByText(mockSuggestions.suggestions[0].rule.key)).toBeVisible()
  expect(body).toEqual(mockSuggestions.suggestions[0].rule)
})

it('displays the returned source, rankings, tiers, hypothesis and historical uplift', async () => {
  const hypothesis = mockSuggestions.suggestions[0].rule.key
  let body: unknown
  server.use(http.post(`${appApiUrl}/insights:run`, async ({ request }) => {
    body = await request.json()
    return HttpResponse.json({ ...mockInsight, hypotheses: [hypothesis] })
  }))
  render(<AppProviders><InsightsPage /></AppProviders>)
  const user = userEvent.setup()
  await user.selectOptions(screen.getByRole('combobox', { name: 'Requested source' }), 'live')
  await user.click(screen.getByRole('button', { name: 'Run insights' }))
  expect(await screen.findByText(hypothesis)).toBeVisible()
  expect(body).toEqual({ source: 'live' })
  expect(screen.getByText('offline')).toBeVisible()
  expect(screen.getByRole('rowheader', { name: 'ai_edits_first_day' })).toBeVisible()
  expect(screen.getByText('f_ai_enhance_tier')).toBeVisible()
  expect(screen.getByText(/candidate for an a\/b test/i)).toBeVisible()
  expect(screen.getByRole('heading', { name: 'Historical randomized uplift' })).toBeVisible()
})

it('explains the runtime configuration error for Insights', async () => {
  server.use(http.get(`${appApiUrl}/insights/latest`, () => HttpResponse.json({
    error: { code: 'brain_not_configured', message: 'Unavailable.' },
  }, { status: 503 })))
  render(<AppProviders><InsightsPage /></AppProviders>)
  expect(await screen.findByRole('alert')).toHaveTextContent('Brain runtime is configured on the server')
})

it('explains the provider configuration error for suggestions', async () => {
  server.use(http.post(`${appApiUrl}/rules:suggest`, () => HttpResponse.json({
    error: { code: 'llm_not_configured', message: 'Unavailable.' },
  }, { status: 503 })))
  render(<AppProviders><MetricsPage /></AppProviders>)
  await userEvent.setup().click(screen.getByRole('button', { name: 'Suggest with AI' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('model provider is configured on the server')
})

it('labels historical uplift with the outcome window of the matching proposal', async () => {
  server.use(http.get(`${appApiUrl}/proposals`, () => HttpResponse.json([
    { ...mockProposal, expected_effect: { ...mockProposal.expected_effect, metric: 'net_revenue_30d' } },
  ])))
  render(<AppProviders><InsightsPage /></AppProviders>)
  expect(await screen.findByText(/30-day net revenue per user, after refunds/)).toBeVisible()
})
