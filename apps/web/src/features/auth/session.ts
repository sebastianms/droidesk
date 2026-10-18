import type { components } from '../../api/schema'
import { isRole, type User } from './access'

export interface Session {
  token: string
  expiresAt: string
  user: User
}

const STORAGE_KEY = 'droidesk.session'

export function saveSession(login: components['schemas']['LoginResponse']): void {
  const session: Session = { token: login.access_token, expiresAt: login.expires_at, user: login.user }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

export function clearSession(): void {
  sessionStorage.removeItem(STORAGE_KEY)
}

export function getSession(): Session | null {
  const session = readStoredSession()
  return session && !isExpired(session) ? session : null
}

function readStoredSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (raw === null) return null

    const parsed: unknown = JSON.parse(raw)
    return isSession(parsed) ? parsed : null
  } catch {
    return null
  }
}

function isExpired(session: Session): boolean {
  return Date.parse(session.expiresAt) <= Date.now()
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isSession(value: unknown): value is Session {
  return (
    isRecord(value) &&
    typeof value.token === 'string' &&
    typeof value.expiresAt === 'string' &&
    !Number.isNaN(Date.parse(value.expiresAt)) &&
    isUser(value.user)
  )
}

function isUser(value: unknown): value is User {
  return (
    isRecord(value) &&
    typeof value.id === 'number' &&
    typeof value.username === 'string' &&
    typeof value.name === 'string' &&
    typeof value.email === 'string' &&
    isRole(value.role)
  )
}
