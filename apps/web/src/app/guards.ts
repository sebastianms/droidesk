import { type LoaderFunction, type MiddlewareFunction, redirect } from 'react-router'
import { homePathFor, LOGIN_PATH, type Role } from '../features/auth/access'
import { getSession, type Session } from '../features/auth/session'

function sessionOrLogin(): Session {
  const session = getSession()
  if (!session) throw redirect(LOGIN_PATH)
  return session
}

export const requireSession: MiddlewareFunction = () => {
  sessionOrLogin()
}

export const requireRole =
  (role: Role): MiddlewareFunction =>
  () => {
    const { user } = sessionOrLogin()
    if (user.role !== role) throw redirect(homePathFor(user.role))
  }

export const redirectToHome: LoaderFunction = () => {
  const session = getSession()
  return redirect(session ? homePathFor(session.user.role) : LOGIN_PATH)
}

export const skipLoginIfSignedIn: LoaderFunction = () => {
  const session = getSession()
  return session ? redirect(homePathFor(session.user.role)) : null
}
