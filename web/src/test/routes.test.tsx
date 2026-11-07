import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AppProviders } from '../app/AppProviders'
import { AppRoutes } from '../app/AppRoutes'

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
})
