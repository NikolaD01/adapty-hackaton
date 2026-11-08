import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest'
import { AppProviders } from '../app/AppProviders'
import { EventsPage } from '../features/behavioral/EventsPage'
import { createHandlers } from '../mocks/handlers'
import { appApiUrl, appWrite } from '../shared/api'
import { freeUser } from '../mocks/fixtures'

const server = setupServer(...createHandlers())
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers(...createHandlers()))
afterAll(() => server.close())

it('saves the feature and event payloads and links the event to its features', async () => {
  let featureBody: unknown
  let eventBody: unknown
  server.use(
    http.post(`${appApiUrl}/features`, async ({ request }) => {
      featureBody = await request.clone().json()
      return undefined
    }),
    http.post(`${appApiUrl}/event-types`, async ({ request }) => {
      eventBody = await request.clone().json()
      return undefined
    }),
  )
  render(<AppProviders><EventsPage /></AppProviders>)
  const user = userEvent.setup()
  await user.click(screen.getByText('Add feature'))
  const feature = within(screen.getByRole('group', { name: 'Feature details' }))
  fireEvent.change(feature.getByRole('textbox', { name: 'Key' }), { target: { value: 'retouch' } })
  fireEvent.change(feature.getByRole('textbox', { name: 'Name' }), { target: { value: 'Retouch' } })
  fireEvent.change(feature.getByRole('textbox', { name: 'Description' }), { target: { value: 'Retouch a photo.' } })
  fireEvent.change(feature.getByRole('textbox', { name: 'Plans (comma-separated)' }), { target: { value: 'premium, pro, premium' } })
  await user.click(feature.getByRole('button', { name: 'Save feature' }))
  expect(await screen.findByText('Retouch saved.')).toBeVisible()
  expect(featureBody).toEqual({ key: 'retouch', name: 'Retouch', description: 'Retouch a photo.', plans: ['premium', 'pro'] })

  await user.click(screen.getByText('Add event'))
  const event = within(screen.getByRole('group', { name: 'Event details' }))
  fireEvent.change(event.getByRole('textbox', { name: 'Key' }), { target: { value: 'photo_retouch' } })
  fireEvent.change(event.getByRole('textbox', { name: 'Name' }), { target: { value: 'Photo retouched' } })
  fireEvent.change(event.getByRole('textbox', { name: 'Description' }), { target: { value: 'The photo was retouched.' } })
  await user.selectOptions(event.getByRole('listbox', { name: 'Features (up to five)' }), ['retouch', 'photo_import'])
  await user.click(event.getByRole('button', { name: 'Save event' }))
  expect(await screen.findByText('Photo retouched saved.')).toBeVisible()
  expect(eventBody).toEqual({
    key: 'photo_retouch', name: 'Photo retouched', description: 'The photo was retouched.',
    features: expect.arrayContaining(['retouch', 'photo_import']),
  })
  expect(screen.getAllByText(/Events · .*Photo retouched/)).toHaveLength(2)
})

it('shows the selected user’s seven-day feature counter', async () => {
  await appWrite('/events', 'POST', { events: [
    { event_id: 'demo-event', customer_user_id: freeUser, key: 'photo_import', occurred_at: new Date().toISOString(), props: {} },
  ] })
  render(<AppProviders><EventsPage /></AppProviders>)
  const counter = await screen.findByText('Uses in the last 7 days · 1')
  expect(counter).toBeVisible()
  await userEvent.setup().selectOptions(screen.getByRole('combobox', { name: 'Activity for' }), 'lumen_282506_00000')
  expect(await screen.findAllByText('Uses in the last 7 days · 0')).toHaveLength(4)
})
