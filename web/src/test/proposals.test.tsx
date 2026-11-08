import { render, screen } from '@testing-library/react'
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
  expect(await screen.findByText('30%')).toBeVisible()
  expect(payload).toEqual({ holdout_pct: 30 })
  expect(screen.getByText('Edit history')).toBeVisible()
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
  expect(await screen.findByText(/autopilot can start eligible tests/i)).toBeVisible()
  expect(payload).toEqual({ ...mockSettings, mode: 'autopilot' })
})
