import { afterEach, describe, expect, it, vi } from 'vitest'
import { agentElena } from '../../test/helpers'
import { clearSession, getSession, saveSession } from './session'

const STORAGE_KEY = 'droidesk.session'

function login(expiresAt: string) {
  return { access_token: 'abc.def.ghi', token_type: 'bearer' as const, expires_at: expiresAt, user: agentElena }
}

function storedWith(userOverrides: Record<string, unknown>): string {
  return JSON.stringify({
    token: 't',
    expiresAt: '2999-01-01T00:00:00Z',
    user: { ...agentElena, ...userOverrides },
  })
}

describe('session', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('returns null when nobody has signed in', () => {
    expect(getSession()).toBeNull()
  })

  it('stores the token and the user from the login response', () => {
    saveSession(login('2999-01-01T00:00:00Z'))

    expect(getSession()).toEqual({ token: 'abc.def.ghi', expiresAt: '2999-01-01T00:00:00Z', user: agentElena })
  })

  it('treats blocked storage as no session', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('El almacenamiento está bloqueado.', 'SecurityError')
    })

    expect(getSession()).toBeNull()
  })

  it('forgets the session when it is cleared', () => {
    saveSession(login('2999-01-01T00:00:00Z'))

    clearSession()

    expect(getSession()).toBeNull()
  })

  it('ignores the session once its expiration time has passed', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-19T12:00:00Z'))
    saveSession(login('2026-10-19T12:00:00Z'))

    expect(getSession()).toBeNull()
  })

  it('reading an expired session does not erase it', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-19T12:00:00Z'))
    saveSession(login('2026-10-19T12:00:00Z'))

    getSession()

    expect(sessionStorage.getItem(STORAGE_KEY)).not.toBeNull()
  })

  it('keeps the session until the last moment before it expires', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-19T11:59:59Z'))
    saveSession(login('2026-10-19T12:00:00Z'))

    expect(getSession()).not.toBeNull()
  })

  it.each([
    ['text that is not JSON', '{not json'],
    ['a JSON value that is not an object', '"hello"'],
    ['null', 'null'],
    ['an object without a token', JSON.stringify({ expiresAt: '2999-01-01T00:00:00Z', user: agentElena })],
    ['an invalid expiration date', JSON.stringify({ token: 't', expiresAt: 'tomorrow', user: agentElena })],
    ['an unknown role', storedWith({ role: 'admin' })],
    ['a missing user', JSON.stringify({ token: 't', expiresAt: '2999-01-01T00:00:00Z' })],
    ['a user without an id', storedWith({ id: undefined })],
    ['a user without a username', storedWith({ username: undefined })],
    ['a user without an email', storedWith({ email: undefined })],
    ['a user whose id is not a number', storedWith({ id: '5' })],
  ])('ignores a stored session that is %s', (_case, raw) => {
    sessionStorage.setItem(STORAGE_KEY, raw)

    expect(getSession()).toBeNull()
  })
})
