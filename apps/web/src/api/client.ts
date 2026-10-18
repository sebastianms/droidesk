import createFetchClient, { type Middleware } from 'openapi-fetch'
import createClient from 'openapi-react-query'
import { LOGIN_PATH } from '../features/auth/access'
import { clearSession, getSession } from '../features/auth/session'
import type { paths } from './schema'

const authMiddleware: Middleware = {
  onRequest({ request }) {
    const session = getSession()
    if (session) request.headers.set('Authorization', `Bearer ${session.token}`)
    return request
  },
  onResponse({ response }) {
    if (response.status === 401) {
      clearSession()
      if (window.location.pathname !== LOGIN_PATH) window.location.assign(LOGIN_PATH)
    }
  },
}

export const apiClient = createFetchClient<paths>({
  baseUrl: window.location.origin,
  fetch: (request) => globalThis.fetch(request),
})
apiClient.use(authMiddleware)

export const $api = createClient(apiClient)
