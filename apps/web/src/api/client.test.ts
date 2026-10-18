import { afterEach, describe, expect, it, vi } from 'vitest'
import { getSession } from '../features/auth/session'
import { agentElena, jsonResponse, signInAs, stubApi } from '../test/helpers'
import { apiClient } from './client'

describe('apiClient', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends the session token as a Bearer credential', async () => {
    const fetchMock = stubApi({ 'GET /api/v1/me': () => jsonResponse(agentElena) })
    signInAs(agentElena)

    await apiClient.GET('/api/v1/me')

    const [request] = fetchMock.mock.calls[0] ?? []
    expect(request?.headers.get('Authorization')).toBe('Bearer token-5')
  })

  it('sends no credential when nobody has signed in', async () => {
    const fetchMock = stubApi({ 'POST /api/v1/auth/login': () => jsonResponse(agentElena) })

    await apiClient.POST('/api/v1/auth/login', {
      body: { username: 'elena.vidal', password: 'cualquiera' },
    })

    const [request] = fetchMock.mock.calls[0] ?? []
    expect(request?.headers.has('Authorization')).toBe(false)
  })

  it('ends the session and goes back to the login screen on a 401', async () => {
    const assign = vi.fn()
    vi.stubGlobal('location', { origin: window.location.origin, pathname: '/agent', assign })
    stubApi({ 'GET /api/v1/me': () => jsonResponse({ code: 'not_authenticated', message: 'Sesión vencida.' }, 401) })
    signInAs(agentElena)

    const { response, error } = await apiClient.GET('/api/v1/me')

    expect(response.status).toBe(401)
    expect(error).toEqual({ code: 'not_authenticated', message: 'Sesión vencida.' })
    expect(getSession()).toBeNull()
    expect(assign).toHaveBeenCalledWith('/login')
  })

  it('does not reload the login screen when a 401 arrives while already there', async () => {
    const assign = vi.fn()
    vi.stubGlobal('location', { origin: window.location.origin, pathname: '/login', assign })
    stubApi({ 'GET /api/v1/me': () => jsonResponse({ code: 'not_authenticated', message: 'Sesión vencida.' }, 401) })

    await apiClient.GET('/api/v1/me')

    expect(assign).not.toHaveBeenCalled()
  })
})
