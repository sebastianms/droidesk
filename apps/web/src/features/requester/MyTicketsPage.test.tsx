import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ticketSummary } from '../../test/fixtures'
import { jsonResponse, renderRoutes, requesterAna, signInAs, stubApi } from '../../test/helpers'
import { formatDateTime } from '../tickets/dates'
import { MyTicketsPage } from './MyTicketsPage'

const TICKETS = 'GET /api/v1/tickets'

function renderMyTickets() {
  signInAs(requesterAna)
  return renderRoutes(
    [
      { path: '/requester', element: <MyTicketsPage /> },
      { path: '/requester/new', element: <p>Formulario de nuevo ticket</p> },
      { path: '/tickets/:ticketId', element: <p>Detalle del ticket</p> },
    ],
    '/requester',
  )
}

describe('MyTicketsPage', () => {
  it('asks only for the tickets of the requester', async () => {
    const fetchMock = stubApi({ [TICKETS]: () => jsonResponse([]) })

    renderMyTickets()
    await screen.findByText(/todavía no hay tickets/)

    const [request] = fetchMock.mock.calls[0]
    expect(new URL(request.url).searchParams.get('view')).toBe('mine')
  })

  it('says it is loading until the tickets arrive', async () => {
    stubApi({ [TICKETS]: () => jsonResponse([]) })

    renderMyTickets()

    expect(screen.getByRole('status')).toHaveTextContent('Bip-bup: cargando tus tickets...')
    await screen.findByText(/todavía no hay tickets/)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('invites the requester to create a first ticket when there are none', async () => {
    stubApi({ [TICKETS]: () => jsonResponse([]) })

    renderMyTickets()

    expect(screen.getByRole('heading', { name: 'Mis tickets' })).toBeInTheDocument()
    expect(await screen.findByText(/todavía no hay tickets/)).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('lists the tickets in the order the API gives them, the newest first', async () => {
    stubApi({
      [TICKETS]: () =>
        jsonResponse([
          ticketSummary({ id: 3, title: 'El más reciente' }),
          ticketSummary({ id: 2, title: 'El del medio' }),
          ticketSummary({ id: 1, title: 'El más antiguo' }),
        ]),
    })

    renderMyTickets()

    const items = await screen.findAllByRole('listitem')
    expect(items.map((item) => within(item).getByRole('link').textContent)).toEqual([
      'El más reciente',
      'El del medio',
      'El más antiguo',
    ])
  })

  it('shows each ticket with its status, priority, category, creation date and SLA', async () => {
    stubApi({
      [TICKETS]: () =>
        jsonResponse([
          ticketSummary({
            id: 7,
            title: 'Pantalla negra',
            status: 'in_progress',
            priority: 'critical',
            category: { id: 1, name: 'Hardware' },
            assignee: { id: 5, name: 'Elena Vidal' },
            created_at: '2026-10-19T13:05:00Z',
            sla: { state: 'at_risk', due_at: '2026-10-19T17:00:00Z' },
          }),
        ]),
    })

    renderMyTickets()

    const item = await screen.findByRole('listitem')
    expect(within(item).getByText('En progreso')).toBeVisible()
    expect(within(item).getByText('Crítica')).toBeVisible()
    expect(within(item).getByText('Hardware')).toBeVisible()
    expect(within(item).getByText('Elena Vidal')).toBeVisible()
    expect(within(item).getByText('Fecha de creación')).toBeVisible()
    expect(within(item).queryByText('Solicitante')).not.toBeInTheDocument()
    expect(within(item).getByText(formatDateTime('2026-10-19T13:05:00Z'))).toBeVisible()
    expect(within(item).getByText('Por vencer')).toBeVisible()
    expect(within(item).getByText(formatDateTime('2026-10-19T17:00:00Z'))).toBeVisible()
  })

  it('shows how many comments each ticket has, in words', async () => {
    stubApi({
      [TICKETS]: () =>
        jsonResponse([
          ticketSummary({ id: 3, title: 'Con varios', comment_count: 3 }),
          ticketSummary({ id: 2, title: 'Con uno', comment_count: 1 }),
          ticketSummary({ id: 1, title: 'Sin ninguno', comment_count: 0 }),
        ]),
    })

    renderMyTickets()

    const items = await screen.findAllByRole('listitem')
    const counts = items.map((item) => within(item).getByText(/comentario/).textContent)
    expect(counts).toEqual(['3 comentarios', '1 comentario', 'Sin comentarios'])
  })

  it('says "Sin asignar" for a ticket nobody has taken', async () => {
    stubApi({ [TICKETS]: () => jsonResponse([ticketSummary({ assignee: null })]) })

    renderMyTickets()

    expect(await screen.findByText('Sin asignar')).toBeVisible()
  })

  it('shows no SLA state for a cancelled ticket', async () => {
    stubApi({
      [TICKETS]: () => jsonResponse([ticketSummary({ status: 'cancelled', sla: { state: null, due_at: null } })]),
    })

    renderMyTickets()

    expect(await screen.findByText('Cancelado')).toBeVisible()
    expect(screen.getByText('No aplica')).toBeVisible()
  })

  it('opens the ticket from its title', async () => {
    stubApi({ [TICKETS]: () => jsonResponse([ticketSummary({ id: 42 })]) })
    const { router } = renderMyTickets()

    await userEvent.click(await screen.findByRole('link', { name: 'No puedo entrar a la VPN' }))

    expect(await screen.findByText('Detalle del ticket')).toBeVisible()
    expect(router.state.location.pathname).toBe('/tickets/42')
  })

  it('offers to create a new ticket', async () => {
    stubApi({ [TICKETS]: () => jsonResponse([]) })
    const { router } = renderMyTickets()

    await userEvent.click(screen.getByRole('link', { name: 'Nuevo ticket' }))

    expect(await screen.findByText('Formulario de nuevo ticket')).toBeVisible()
    expect(router.state.location.pathname).toBe('/requester/new')
  })

  it('still offers a new ticket when the tickets could not be loaded', async () => {
    stubApi({ [TICKETS]: () => jsonResponse({ detail: 'boom' }, 500) })

    renderMyTickets()
    await screen.findByRole('alert')

    expect(screen.getByRole('link', { name: 'Nuevo ticket' })).toBeVisible()
  })

  it('shows a generic message when loading fails for an unknown reason', async () => {
    stubApi({ [TICKETS]: () => jsonResponse({ detail: 'boom' }, 500) })

    renderMyTickets()

    expect(await screen.findByRole('alert')).toHaveTextContent('Bip-bup: no pude cargar tus tickets. Intenta de nuevo.')
    expect(screen.queryByText(/todavía no hay tickets/)).not.toBeInTheDocument()
  })

  it('shows the message of the API when it explains the failure', async () => {
    stubApi({ [TICKETS]: () => jsonResponse({ code: 'forbidden', message: 'No puedes ver esta vista.' }, 403) })

    renderMyTickets()

    expect(await screen.findByRole('alert')).toHaveTextContent('No puedes ver esta vista.')
  })
})
