import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { agentElena, renderRoutes, requesterAna, signInAs } from '../test/helpers'
import { routes } from './router'

describe('route guards', () => {
  it.each(['/requester', '/agent', '/'])('sends an anonymous visitor from %s to the login screen', async (path) => {
    const { router } = renderRoutes(routes, path)

    expect(await screen.findByRole('heading', { name: 'DroiDesk' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('sends a visitor with an expired session to the login screen', async () => {
    signInAs(requesterAna, '2020-01-01T00:00:00Z')

    const { router } = renderRoutes(routes, '/requester')

    expect(await screen.findByRole('heading', { name: 'DroiDesk' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('lets a requester into their own tickets', async () => {
    signInAs(requesterAna)

    renderRoutes(routes, '/requester')

    expect(await screen.findByRole('heading', { name: 'Mis tickets' })).toBeInTheDocument()
  })

  it('lets an agent into the queue', async () => {
    signInAs(agentElena)

    renderRoutes(routes, '/agent')

    expect(await screen.findByRole('heading', { name: 'Cola de tickets' })).toBeInTheDocument()
  })

  it('keeps a requester out of the agent queue and sends them to their tickets', async () => {
    signInAs(requesterAna)

    const { router } = renderRoutes(routes, '/agent')

    expect(await screen.findByRole('heading', { name: 'Mis tickets' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Cola de tickets' })).not.toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/requester')
  })

  it('keeps an agent out of the requester view and sends them to the queue', async () => {
    signInAs(agentElena)

    const { router } = renderRoutes(routes, '/requester')

    expect(await screen.findByRole('heading', { name: 'Cola de tickets' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/agent')
  })

  it.each([
    ['requester', requesterAna, '/requester'],
    ['agent', agentElena, '/agent'],
  ])('sends a signed-in %s who opens the login screen to their home', async (_role, user, home) => {
    signInAs(user)

    const { router } = renderRoutes(routes, '/login')

    await waitFor(() => expect(router.state.location.pathname).toBe(home))
  })

  it('sends a signed-in user from an unknown path to their home', async () => {
    signInAs(agentElena)

    const { router } = renderRoutes(routes, '/does-not-exist')

    expect(await screen.findByRole('heading', { name: 'Cola de tickets' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/agent')
  })
})
