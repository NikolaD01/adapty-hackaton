import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest'
import { AppProviders } from '../app/AppProviders'
import { ProposalsPage } from '../features/behavioral/ProposalsPage'
import { mockProposal, mockSettings } from '../mocks/fixtures'
import { createHandlers } from '../mocks/handlers'
import { apiUrl, appApiUrl } from '../shared/api'
import { proposalStatuses } from '../types/targeting'

const server = setupServer(...createHandlers())
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers(...createHandlers()))
afterAll(() => server.close())

function renderProposals() {
  return render(<AppProviders><MemoryRouter><ProposalsPage /></MemoryRouter></AppProviders>)
}

it.each(proposalStatuses)('shows the %s proposal status with the right approval controls', async (status) => {
  server.use(http.get(`${appApiUrl}/proposals`, () => HttpResponse.json([{ ...mockProposal, status }])))
  renderProposals()
  expect(await screen.findByText(new RegExp(`^${status.replace('_', ' ')}$`, 'i'))).toBeInTheDocument()
  if (status === 'executing') expect(screen.getByRole('button', { name: 'Approve' })).toBeDisabled()
  if (status === 'awaiting_publish') {
    expect(screen.getByText(/publish the new paywall in adapty/i)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Continue after publishing' })).toBeEnabled()
  }
})

it('edits only changed whitelisted fields and renders the saved state', async () => {
  let payload: unknown
  server.use(http.patch(`${apiUrl}/proposals/:id`, async ({ request }) => {
    payload = await request.clone().json()
    return undefined
  }))
  renderProposals()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Edit' }))
  const input = screen.getByRole('spinbutton', { name: 'Holdout (%)' })
  await user.clear(input)
  await user.type(input, '30')
  await user.click(screen.getByRole('button', { name: 'Save changes' }))
  expect(await screen.findByText(/70% of this group see the offer and 30% keep the current paywall/)).toBeVisible()
  await user.click(screen.getByText('Technical details'))
  expect(screen.getByText('30%')).toBeVisible()
  expect(payload).toEqual({ holdout_pct: 30 })
  const history = within(screen.getByRole('table', { name: 'Edit history' }))
  expect(history.getByRole('rowheader', { name: 'holdout_pct' })).toBeVisible()
  expect(history.getByRole('cell', { name: '20' })).toBeVisible()
  expect(history.getByRole('cell', { name: '30' })).toBeVisible()
})

it('disables approval while the request runs and shows the actual result', async () => {
  let finish!: () => void
  const hold = new Promise<void>((resolve) => { finish = resolve })
  let count = 0
  server.use(http.post(`${apiUrl}/proposals/:operation`, async () => {
    count++
    await hold
    return undefined
  }))
  renderProposals()
  const user = userEvent.setup()
  const approve = await screen.findByRole('button', { name: 'Approve' })
  try {
    await user.click(approve)
    expect(approve).toBeDisabled()
    await user.click(approve)
    expect(count).toBe(1)
  } finally {
    finish()
  }
  expect(await screen.findByText('Live')).toBeVisible()
})

it('rejects a draft with a reason', async () => {
  renderProposals()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Reject' }))
  await user.type(screen.getByRole('textbox', { name: 'Reason' }), 'Use a smaller cohort.')
  await user.click(screen.getByRole('button', { name: 'Confirm rejection' }))
  expect(await screen.findByText('Rejected')).toBeVisible()
})

it('preserves autopilot limits when switching modes and shows the warning', async () => {
  let payload: unknown
  server.use(http.put(`${appApiUrl}/settings`, async ({ request }) => {
    payload = await request.clone().json()
    return undefined
  }))
  renderProposals()
  await userEvent.setup().selectOptions(await screen.findByRole('combobox', { name: 'Mode' }), 'autopilot')
  expect(await screen.findByText(/autopilot starts tests by itself/i)).toBeVisible()
  expect(payload).toEqual({ ...mockSettings, mode: 'autopilot' })
})

it('shows the net revenue window returned by the API', async () => {
  server.use(http.get(`${appApiUrl}/proposals`, () => HttpResponse.json([
    { ...mockProposal, expected_effect: { ...mockProposal.expected_effect, metric: 'net_revenue_30d' } },
  ])))
  renderProposals()
  expect(await screen.findByText('Expected net revenue per user over 30 days')).toBeVisible()
})

it('keeps the edit draft while switching between proposals', async () => {
  server.use(http.get(`${appApiUrl}/proposals`, () => HttpResponse.json([
    mockProposal,
    {
      ...mockProposal, proposal_id: 'pr_second', segment_key: 'other_editors', status: 'live',
      evidence: { ...mockProposal.evidence, segment_conditions: [{ field: 'ai_enhance_uses_7d', op: '>', value: 3 }] },
    },
  ])))
  renderProposals()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Edit' }))
  const input = screen.getByRole('spinbutton', { name: 'Holdout (%)' })
  await user.clear(input)
  await user.type(input, '25')

  const second = 'Users who used AI enhance 4 or more times in 7 days, with subscription state never subscribed'
  await user.click(screen.getByRole('button', { name: new RegExp(second) }))
  expect(screen.getByRole('article', { name: second })).toBeVisible()
  expect(screen.queryByRole('spinbutton', { name: 'Holdout (%)' })).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /AI edits first day at least 5/ }))
  expect(screen.getByRole('spinbutton', { name: 'Holdout (%)' })).toHaveValue(25)
})

it('leads with a plain summary and keeps the technical details folded', async () => {
  server.use(http.get(`${appApiUrl}/proposals`, () => HttpResponse.json([{
    ...mockProposal,
    expected_effect: { metric: 'net_revenue_60d', diff: 22.596, ci_low: 2.402, ci_high: 47.9002 },
    evidence: { ...mockProposal.evidence, synthetic: true, n_a: 10, n_b: 10 },
    reason: 'lift 2.013994749445399; holdout lift 1.2361809323776423',
  }])))
  renderProposals()
  const card = await screen.findByRole('article', { name: /AI edits first day at least 5/ })
  expect(within(card).getByRole('heading', { level: 2 })).toHaveTextContent('Users with AI edits first day at least 5')
  expect(within(card).getByText('Offer: show them the “Lifetime anchor” paywall.')).toBeVisible()
  expect(within(card).getByText('Expected net revenue per user over 60 days')).toBeVisible()
  expect(within(card).getByText(/^\+\$22\.60/)).toBeVisible()
  expect(within(card).getByText('likely between $2.40 and $47.90, net of refunds')).toBeVisible()
  expect(within(card).getByText(/Based on 20 users .* treat it as uncertain/)).toBeVisible()
  expect(within(card).getByText('Synthetic demo data.')).toBeVisible()
  expect(within(card).getByText(/lift 2\.013994749445399/)).not.toBeVisible()
})
