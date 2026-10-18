import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ticketDetail } from '../../test/fixtures'
import { agentElena, jsonResponse, renderRoutes, requesterAna, signInAs, stubApi } from '../../test/helpers'
import type { User } from '../auth/access'
import { formatDateTime } from './dates'
import { TICKET_ROUTE } from './paths'
import { TicketDetailPage } from './TicketDetailPage'

const DETAIL = 'GET /api/v1/tickets/42'
const TRANSITION = 'POST /api/v1/tickets/42/transitions'

function renderDetail(path = '/tickets/42', user: User = requesterAna) {
  signInAs(user)
  return renderRoutes(
    [
      { path: TICKET_ROUTE, element: <TicketDetailPage /> },
      { path: '/requester', element: <p>Vista Mis tickets</p> },
      { path: '/agent', element: <p>Vista de la cola</p> },
    ],
    path,
  )
}

describe('TicketDetailPage', () => {
  describe('a ticket', () => {
    it('says it is loading until the ticket arrives', async () => {
      stubApi({ [DETAIL]: () => jsonResponse(ticketDetail()) })

      renderDetail()

      expect(screen.getByRole('status')).toHaveTextContent('Bip-bup: cargando el ticket...')
      await screen.findByRole('heading', { name: 'No puedo entrar a la VPN' })
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
    })

    it('shows its title, number and description', async () => {
      stubApi({ [DETAIL]: () => jsonResponse(ticketDetail()) })

      renderDetail()

      expect(await screen.findByRole('heading', { name: 'No puedo entrar a la VPN' })).toBeVisible()
      expect(screen.getByText('Ticket #42')).toBeVisible()
      expect(screen.getByText('Desde esta mañana la VPN rechaza mis credenciales.')).toBeVisible()
    })

    it('shows its status, priority, category, people, dates and SLA', async () => {
      stubApi({
        [DETAIL]: () =>
          jsonResponse(
            ticketDetail({
              status: 'in_progress',
              priority: 'critical',
              category: { id: 1, name: 'Hardware' },
              assignee: { id: 5, name: 'Elena Vidal' },
              sla: { state: 'breached', due_at: '2026-10-19T17:00:00Z' },
              allowed_actions: [],
            }),
          ),
      })

      renderDetail()

      await screen.findByRole('heading', { name: 'No puedo entrar a la VPN' })
      const facts = within(screen.getByRole('region', { name: 'Datos' }))
      expect(facts.getByText('En progreso')).toBeVisible()
      expect(facts.getByText('Crítica')).toBeVisible()
      expect(facts.getByText('Hardware')).toBeVisible()
      expect(facts.getByText('Ana Rojas')).toBeVisible()
      expect(facts.getByText('Elena Vidal')).toBeVisible()
      expect(facts.getByText(formatDateTime('2026-10-19T13:05:00Z'))).toBeVisible()
      expect(facts.getByText('Vencido')).toBeVisible()
      expect(facts.getByText(formatDateTime('2026-10-19T17:00:00Z'))).toBeVisible()
    })

    it('says "Sin asignar" for a ticket nobody has taken', async () => {
      stubApi({ [DETAIL]: () => jsonResponse(ticketDetail({ assignee: null })) })

      renderDetail()

      expect(await screen.findByText('Sin asignar')).toBeVisible()
    })

    it('shows when it was resolved, closed or cancelled only if it was', async () => {
      stubApi({
        [DETAIL]: () =>
          jsonResponse(
            ticketDetail({
              status: 'closed',
              resolved_at: '2026-10-20T10:00:00Z',
              closed_at: '2026-10-21T11:30:00Z',
              allowed_actions: [],
            }),
          ),
      })

      renderDetail()

      expect(await screen.findByText('Fecha de resolución')).toBeVisible()
      expect(screen.getByText(formatDateTime('2026-10-20T10:00:00Z'))).toBeVisible()
      expect(screen.getByText('Fecha de cierre')).toBeVisible()
      expect(screen.getByText(formatDateTime('2026-10-21T11:30:00Z'))).toBeVisible()
      expect(screen.queryByText('Fecha de cancelación')).not.toBeInTheDocument()
    })

    it('shows a cancelled ticket with its date and no SLA', async () => {
      stubApi({
        [DETAIL]: () =>
          jsonResponse(
            ticketDetail({
              status: 'cancelled',
              cancelled_at: '2026-10-19T15:00:00Z',
              sla: { state: null, due_at: null },
              allowed_actions: [],
            }),
          ),
      })

      renderDetail()

      expect(await screen.findByText('Fecha de cancelación')).toBeVisible()
      expect(screen.getByText('Cancelado')).toBeVisible()
      expect(screen.getByText(formatDateTime('2026-10-19T15:00:00Z'))).toBeVisible()
      expect(screen.getByText('No aplica')).toBeVisible()
    })

    it('shows the description as plain text, without interpreting it', async () => {
      const markup = '<img src=x onerror="alert(1)"> **negrita** &amp;'
      stubApi({ [DETAIL]: () => jsonResponse(ticketDetail({ description: markup })) })

      renderDetail()

      expect(await screen.findByText(markup)).toBeVisible()
      expect(screen.queryByRole('img')).not.toBeInTheDocument()
    })

    it('asks the API for the ticket of the address', async () => {
      const fetchMock = stubApi({ [DETAIL]: () => jsonResponse(ticketDetail()) })

      renderDetail()
      await screen.findByRole('heading', { name: 'No puedo entrar a la VPN' })

      expect(new URL(fetchMock.mock.calls[0][0].url).pathname).toBe('/api/v1/tickets/42')
    })
  })

  describe('going back', () => {
    it('takes a requester back to "Mis tickets"', async () => {
      stubApi({ [DETAIL]: () => jsonResponse(ticketDetail()) })
      const { router } = renderDetail()

      await userEvent.click(await screen.findByRole('link', { name: 'Volver a Mis tickets' }))

      expect(await screen.findByText('Vista Mis tickets')).toBeVisible()
      expect(router.state.location.pathname).toBe('/requester')
    })

    it('takes an agent back to the queue', async () => {
      stubApi({ [DETAIL]: () => jsonResponse(ticketDetail()) })
      const { router } = renderDetail('/tickets/42', agentElena)

      await userEvent.click(await screen.findByRole('link', { name: 'Volver a la cola' }))

      expect(await screen.findByText('Vista de la cola')).toBeVisible()
      expect(router.state.location.pathname).toBe('/agent')
    })
  })

  describe('a ticket that cannot be shown', () => {
    it('says "No encontrado" when the ticket does not exist or is somebody else\'s', async () => {
      stubApi({ [DETAIL]: () => jsonResponse({ code: 'not_found', message: 'El ticket no existe.' }, 404) })

      renderDetail()

      expect(await screen.findByRole('heading', { name: 'No encontrado' })).toBeVisible()
      expect(screen.getByText('El ticket no existe.')).toBeVisible()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('offers the way back to the home of the role from the "No encontrado" page', async () => {
      stubApi({ [DETAIL]: () => jsonResponse({ code: 'not_found', message: 'El ticket no existe.' }, 404) })
      const { router } = renderDetail()

      await userEvent.click(await screen.findByRole('link', { name: 'Volver a Mis tickets' }))

      expect(await screen.findByText('Vista Mis tickets')).toBeVisible()
      expect(router.state.location.pathname).toBe('/requester')
    })

    it('says "No encontrado" without asking the API when the address has no valid number', async () => {
      const fetchMock = stubApi({})

      renderDetail('/tickets/abc')

      expect(await screen.findByRole('heading', { name: 'No encontrado' })).toBeVisible()
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('says "No encontrado" for a number with decimals', async () => {
      stubApi({})

      renderDetail('/tickets/4.5')

      expect(await screen.findByRole('heading', { name: 'No encontrado' })).toBeVisible()
    })

    it('shows a generic failure, not "No encontrado", when the ticket could not be loaded', async () => {
      stubApi({ [DETAIL]: () => jsonResponse({ detail: 'boom' }, 500) })

      renderDetail()

      expect(await screen.findByRole('alert')).toHaveTextContent('Bip-bup: no pude cargar el ticket. Intenta de nuevo.')
      expect(screen.queryByRole('heading', { name: 'No encontrado' })).not.toBeInTheDocument()
    })

    it('shows the message of the API when it explains the failure', async () => {
      stubApi({ [DETAIL]: () => jsonResponse({ code: 'forbidden', message: 'No puedes ver este ticket.' }, 403) })

      renderDetail()

      expect(await screen.findByRole('alert')).toHaveTextContent('No puedes ver este ticket.')
    })
  })

  describe('actions', () => {
    it('offers the actions the API allows', async () => {
      stubApi({ [DETAIL]: () => jsonResponse(ticketDetail({ allowed_actions: ['cancel', 'comment'] })) })

      renderDetail()

      const actions = within(await screen.findByRole('region', { name: 'Acciones' }))
      expect(actions.getAllByRole('button').map((button) => button.textContent)).toEqual(['Cancelar'])
    })

    it('offers no actions on a ticket that allows none', async () => {
      stubApi({ [DETAIL]: () => jsonResponse(ticketDetail({ status: 'closed', allowed_actions: [] })) })

      renderDetail()

      await screen.findByRole('heading', { name: 'No puedo entrar a la VPN' })
      expect(screen.queryByRole('region', { name: 'Acciones' })).not.toBeInTheDocument()
    })

    it('updates the page with the ticket the API answers after an action', async () => {
      stubApi({
        [DETAIL]: () => jsonResponse(ticketDetail({ status: 'resolved', allowed_actions: ['close', 'reopen'] })),
        [TRANSITION]: () =>
          jsonResponse(ticketDetail({ status: 'closed', closed_at: '2026-10-21T11:30:00Z', allowed_actions: [] })),
      })
      renderDetail()
      await userEvent.click(await screen.findByRole('button', { name: 'Confirmar cierre' }))

      expect(await screen.findByText(formatDateTime('2026-10-21T11:30:00Z'))).toBeVisible()
      expect(within(screen.getByRole('region', { name: 'Datos' })).getByText('Cerrado')).toBeVisible()
      expect(screen.queryByRole('region', { name: 'Acciones' })).not.toBeInTheDocument()
    })

    it('keeps the agent on the ticket once they take it, now in progress and theirs', async () => {
      stubApi({
        [DETAIL]: () => jsonResponse(ticketDetail({ allowed_actions: ['take', 'comment'] })),
        [TRANSITION]: () =>
          jsonResponse(
            ticketDetail({
              status: 'in_progress',
              assignee: { id: 5, name: 'Elena Vidal' },
              allowed_actions: ['hold', 'resolve', 'comment'],
            }),
          ),
      })
      const { router } = renderDetail('/tickets/42', agentElena)
      await userEvent.click(await screen.findByRole('button', { name: 'Tomar' }))

      const facts = within(screen.getByRole('region', { name: 'Datos' }))
      expect(await facts.findByText('En progreso')).toBeVisible()
      expect(facts.getByText('Elena Vidal')).toBeVisible()
      const actions = within(screen.getByRole('region', { name: 'Acciones' }))
      expect(actions.getAllByRole('button').map((button) => button.textContent)).toEqual([
        'Dejar en espera',
        'Resolver',
      ])
      expect(router.state.location.pathname).toBe('/tickets/42')
    })

    it('cancels an open ticket after the confirmation', async () => {
      stubApi({
        [DETAIL]: () => jsonResponse(ticketDetail({ allowed_actions: ['cancel', 'comment'] })),
        [TRANSITION]: () =>
          jsonResponse(
            ticketDetail({
              status: 'cancelled',
              cancelled_at: '2026-10-19T15:00:00Z',
              sla: { state: null, due_at: null },
              allowed_actions: [],
            }),
          ),
      })
      renderDetail()
      await userEvent.click(await screen.findByRole('button', { name: 'Cancelar' }))

      await userEvent.click(screen.getByRole('button', { name: 'Sí, cancelar ticket' }))

      expect(await screen.findByText('No aplica')).toBeVisible()
      expect(within(screen.getByRole('region', { name: 'Datos' })).getByText('Cancelado')).toBeVisible()
    })

    it('explains why an action failed and brings the page up to date, with no action left', async () => {
      let detailRequests = 0
      stubApi({
        [DETAIL]: () =>
          ++detailRequests === 1
            ? jsonResponse(ticketDetail({ allowed_actions: ['cancel'] }))
            : jsonResponse(
                ticketDetail({
                  status: 'in_progress',
                  assignee: { id: 5, name: 'Elena Vidal' },
                  allowed_actions: ['comment'],
                }),
              ),
        [TRANSITION]: () =>
          jsonResponse({ code: 'action_not_allowed', message: 'Un agente ya tomó este ticket.' }, 409),
      })
      renderDetail()
      await userEvent.click(await screen.findByRole('button', { name: 'Cancelar' }))

      await userEvent.click(screen.getByRole('button', { name: 'Sí, cancelar ticket' }))

      expect(await screen.findByText('Un agente ya tomó este ticket.')).toBeVisible()
      await waitFor(() => expect(screen.queryByRole('button', { name: 'Cancelar' })).not.toBeInTheDocument())
      expect(within(screen.getByRole('region', { name: 'Datos' })).getByText('En progreso')).toBeVisible()
      expect(screen.getByText('Un agente ya tomó este ticket.')).toBeVisible()
    })
  })
})
