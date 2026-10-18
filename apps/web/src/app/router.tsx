import type { RouteObject } from 'react-router'
import { QueuePage } from '../features/agent/QueuePage'
import { LoginPage } from '../features/auth/LoginPage'
import { MyTicketsPage } from '../features/requester/MyTicketsPage'
import { NewTicketForm } from '../features/requester/NewTicketForm'
import { NEW_TICKET_PATH, TICKET_ROUTE } from '../features/tickets/paths'
import { TicketDetailPage } from '../features/tickets/TicketDetailPage'
import { AppLayout } from './AppLayout'
import { redirectToHome, requireRole, requireSession, skipLoginIfSignedIn } from './guards'

export const routes: RouteObject[] = [
  { path: '/login', loader: skipLoginIfSignedIn, element: <LoginPage /> },
  {
    element: <AppLayout />,
    middleware: [requireSession],
    children: [
      { path: '/requester', middleware: [requireRole('requester')], element: <MyTicketsPage /> },
      { path: NEW_TICKET_PATH, middleware: [requireRole('requester')], element: <NewTicketForm /> },
      { path: TICKET_ROUTE, element: <TicketDetailPage /> },
      { path: '/agent', middleware: [requireRole('agent')], element: <QueuePage /> },
    ],
  },
  { path: '*', loader: redirectToHome },
]
