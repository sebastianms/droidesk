import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, type RouteObject } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { vi } from 'vitest'
import type { DemoUser, User } from '../features/auth/access'
import { saveSession } from '../features/auth/session'

type Handler = (request: Request) => Response | Promise<Response>

export const requesterAna: User = {
  id: 1,
  username: 'ana.rojas',
  name: 'Ana Rojas',
  email: 'ana.rojas@droidesk.local',
  role: 'requester',
}
export const agentElena: User = {
  id: 5,
  username: 'elena.vidal',
  name: 'Elena Vidal',
  email: 'elena.vidal@droidesk.local',
  role: 'agent',
}

export const demoUsers: DemoUser[] = [
  { username: 'ana.rojas', name: 'Ana Rojas', role: 'requester' },
  { username: 'bruno.castillo', name: 'Bruno Castillo', role: 'requester' },
  { username: 'elena.vidal', name: 'Elena Vidal', role: 'agent' },
]

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

export function stubApi(handlers: Record<string, Handler>) {
  const fetchMock = vi.fn(async (request: Request) => {
    const key = `${request.method} ${new URL(request.url).pathname}`
    const handler = handlers[key]
    if (!handler) throw new Error(`Unexpected request: ${key}`)
    return handler(request)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function signInAs(user: User, expiresAt = '2999-01-01T00:00:00Z'): void {
  saveSession({ access_token: `token-${user.id}`, token_type: 'bearer', expires_at: expiresAt, user })
}

export function renderRoutes(routes: RouteObject[], initialEntry: string) {
  const router = createMemoryRouter(routes, { initialEntries: [initialEntry] })
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router, queryClient }
}
