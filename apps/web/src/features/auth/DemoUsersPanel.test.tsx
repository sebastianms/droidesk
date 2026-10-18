import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { demoUsers, jsonResponse, renderRoutes, stubApi } from '../../test/helpers'
import { DemoUsersPanel } from './DemoUsersPanel'

const USERS = 'GET /api/v1/auth/users'

function renderPanel({ open = true, onPick = vi.fn() } = {}) {
  renderRoutes([{ path: '/', element: <DemoUsersPanel id="demo-users" open={open} onPick={onPick} /> }], '/')
  return onPick
}

describe('DemoUsersPanel', () => {
  it('does not ask for the users while it is closed', () => {
    const fetchMock = stubApi({})

    renderPanel({ open: false })

    expect(fetchMock).not.toHaveBeenCalled()
    expect(document.getElementById('demo-users')).not.toBeVisible()
  })

  it('is a region named by its heading, which explains what the demo users are', async () => {
    stubApi({ [USERS]: () => jsonResponse(demoUsers) })

    renderPanel()

    const panel = await screen.findByRole('region', { name: 'Usuarios de demo' })
    expect(within(panel).getByRole('heading', { name: 'Usuarios de demo' })).toBeVisible()
    expect(panel).toHaveTextContent('cuentas de demostración precargadas para probar DroiDesk')
    expect(panel).toHaveTextContent('los solicitantes crean tickets y los agentes los atienden')
    expect(panel).toHaveTextContent('escribe cualquier contraseña')
  })

  it('keeps the explanation while the users load', () => {
    stubApi({ [USERS]: () => new Promise<Response>(() => {}) })

    renderPanel()

    expect(screen.getByRole('region', { name: 'Usuarios de demo' })).toHaveTextContent('cuentas de demostración')
  })

  it('keeps the explanation when the users cannot be loaded', async () => {
    stubApi({ [USERS]: () => jsonResponse({}, 500) })

    renderPanel()

    await screen.findByRole('alert')
    expect(screen.getByRole('region', { name: 'Usuarios de demo' })).toHaveTextContent('cuentas de demostración')
  })

  it('keeps the explanation when there are no demo users', async () => {
    stubApi({ [USERS]: () => jsonResponse([]) })

    renderPanel()

    await screen.findByText(/no hay usuarios de demo cargados/)
    expect(screen.getByRole('region', { name: 'Usuarios de demo' })).toHaveTextContent('cuentas de demostración')
  })

  it('tells that it is looking for the users while they load', async () => {
    stubApi({ [USERS]: () => new Promise<Response>(() => {}) })

    renderPanel()

    expect(await screen.findByRole('status')).toHaveTextContent('buscando a los usuarios de demo')
  })

  it('groups the users by profile, requesters first', async () => {
    stubApi({ [USERS]: () => jsonResponse(demoUsers) })

    renderPanel()

    const requesters = await screen.findByRole('region', { name: 'Solicitantes' })
    expect(within(requesters).getAllByRole('button')).toHaveLength(2)
    const agents = screen.getByRole('region', { name: 'Agentes' })
    expect(within(agents).getAllByRole('button')).toHaveLength(1)
    expect(screen.getAllByRole('region').map((region) => region.getAttribute('aria-labelledby'))).toEqual([
      'demo-users-heading',
      'demo-users-requester',
      'demo-users-agent',
    ])
  })

  it('shows the name and the username of each user', async () => {
    stubApi({ [USERS]: () => jsonResponse(demoUsers) })

    renderPanel()

    const elena = await screen.findByRole('button', { name: /Elena Vidal/ })
    expect(elena).toHaveTextContent('elena.vidal')
  })

  it('reports the username of the user that was picked', async () => {
    stubApi({ [USERS]: () => jsonResponse(demoUsers) })
    const onPick = renderPanel()

    await userEvent.click(await screen.findByRole('button', { name: /Bruno Castillo/ }))

    expect(onPick).toHaveBeenCalledExactlyOnceWith('bruno.castillo')
  })

  it('leaves out a profile that has no users', async () => {
    stubApi({ [USERS]: () => jsonResponse(demoUsers.filter((user) => user.role === 'agent')) })

    renderPanel()

    await screen.findByRole('region', { name: 'Agentes' })
    expect(screen.queryByRole('region', { name: 'Solicitantes' })).not.toBeInTheDocument()
  })

  it('says so when there are no demo users', async () => {
    stubApi({ [USERS]: () => jsonResponse([]) })

    renderPanel()

    expect(await screen.findByText(/no hay usuarios de demo cargados/)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Solicitantes' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Agentes' })).not.toBeInTheDocument()
  })

  it('lets the user retry when the users cannot be loaded', async () => {
    let attempts = 0
    stubApi({ [USERS]: () => (++attempts === 1 ? jsonResponse({}, 500) : jsonResponse(demoUsers)) })
    renderPanel()

    expect(await screen.findByRole('alert')).toHaveTextContent('no pude cargar los usuarios de demo')
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByRole('button', { name: /Ana Rojas/ })).toBeInTheDocument()
  })
})
