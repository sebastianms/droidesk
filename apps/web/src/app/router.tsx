import type { RouteObject } from 'react-router'
import { QueuePage } from '../features/agent/QueuePage'
import { LoginPage } from '../features/auth/LoginPage'
import { MyTicketsPage } from '../features/requester/MyTicketsPage'
import { AppLayout } from './AppLayout'
import { redirectToHome, requireRole, requireSession, skipLoginIfSignedIn } from './guards'

export const routes: RouteObject[] = [
  { path: '/login', loader: skipLoginIfSignedIn, element: <LoginPage /> },
  {
    element: <AppLayout />,
    middleware: [requireSession],
    children: [
      { path: '/requester', middleware: [requireRole('requester')], element: <MyTicketsPage /> },
      { path: '/agent', middleware: [requireRole('agent')], element: <QueuePage /> },
    ],
  },
  { path: '*', loader: redirectToHome },
]
