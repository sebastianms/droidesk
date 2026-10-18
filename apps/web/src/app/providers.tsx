import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { routes } from './router'

const STALE_TIME_MS = 30_000

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: STALE_TIME_MS, retry: 1 } } })
const router = createBrowserRouter(routes)

export function Providers() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
