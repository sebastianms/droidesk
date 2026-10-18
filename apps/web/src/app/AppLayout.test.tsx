import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { getSession } from '../features/auth/session'
import { agentElena, renderRoutes, requesterAna, signInAs } from '../test/helpers'
import { routes } from './router'

describe('AppLayout', () => {
  it('shows who is signed in and their profile', async () => {
    signInAs(requesterAna)

    renderRoutes(routes, '/requester')

    expect(await screen.findByText('Ana Rojas')).toBeInTheDocument()
    expect(screen.getByText('Solicitante')).toBeInTheDocument()
  })

  it('signs out, clears the query cache and returns to the login screen', async () => {
    signInAs(agentElena)
    const { router, queryClient } = renderRoutes(routes, '/agent')
    const clear = vi.spyOn(queryClient, 'clear')

    await userEvent.click(await screen.findByRole('button', { name: 'Salir' }))

    expect(await screen.findByRole('button', { name: 'Ingresar' })).toBeInTheDocument()
    expect(getSession()).toBeNull()
    expect(clear).toHaveBeenCalledOnce()
    expect(router.state.location.pathname).toBe('/login')
  })
})
