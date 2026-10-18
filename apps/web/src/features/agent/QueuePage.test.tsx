import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ticketDetail, ticketSummary } from '../../test/fixtures'
import { agentElena, jsonResponse, renderRoutes, signInAs, stubApi } from '../../test/helpers'
import { formatDateTime } from '../tickets/dates'
import { TICKET_ROUTE } from '../tickets/paths'
import { TicketDetailPage } from '../tickets/TicketDetailPage'
import type { TicketDetail, TicketSummary, TicketView } from '../tickets/types'
import { QueuePage } from './QueuePage'

const TICKETS = 'GET /api/v1/tickets'
const DETAIL = 'GET /api/v1/tickets/42'
const TRANSITION = 'POST /api/v1/tickets/42/transitions'

type Lists = Partial<Record<TicketView, TicketSummary[]>>

function viewOf(request: Request) {
  return new URL(request.url).searchParams.get('view') as TicketView
}

function stubLists(lists: Lists) {
  return stubApi({ [TICKETS]: (request) => jsonResponse(lists[viewOf(request)] ?? []) })
}

function listRequests(fetchMock: ReturnType<typeof stubApi>) {
  return fetchMock.mock.calls.filter(([request]) => request.method === 'GET' && request.url.includes('?view='))
}

function renderQueue(entry = '/agent') {
  signInAs(agentElena)
  return renderRoutes(
    [
      { path: '/agent', element: <QueuePage /> },
      { path: TICKET_ROUTE, element: <TicketDetailPage /> },
    ],
    entry,
  )
}

function tab(name: string) {
  return screen.getByRole('link', { name })
}

describe('QueuePage', () => {
  describe('the tabs', () => {
    it('opens the queue first, with "Cola" as the current tab', async () => {
      const fetchMock = stubLists({})

      renderQueue()
      await screen.findByText('Bip-bup: la cola está despejada')

      expect(viewOf(fetchMock.mock.calls[0][0])).toBe('queue')
      expect(tab('Cola')).toHaveAttribute('aria-current', 'page')
      expect(tab('Asignados a mí')).not.toHaveAttribute('aria-current')
    })

    it('opens the assigned tickets from the address, so the tab survives a reload', async () => {
      const fetchMock = stubLists({})

      renderQueue('/agent?view=assigned')
      await screen.findByText('Bip-bup: no tienes tickets asignados')

      expect(viewOf(fetchMock.mock.calls[0][0])).toBe('assigned')
      expect(tab('Asignados a mí')).toHaveAttribute('aria-current', 'page')
      expect(tab('Cola')).not.toHaveAttribute('aria-current')
    })

    it('falls back to the queue when the address names a view it does not know', async () => {
      const fetchMock = stubLists({})

      renderQueue('/agent?view=mine')
      await screen.findByText('Bip-bup: la cola está despejada')

      expect(viewOf(fetchMock.mock.calls[0][0])).toBe('queue')
      expect(tab('Cola')).toHaveAttribute('aria-current', 'page')
    })

    it('switches between the queue and the assigned tickets, keeping the choice in the address', async () => {
      stubLists({
        queue: [ticketSummary({ id: 1, title: 'Del resto de la cola' }), ticketSummary({ id: 2, title: 'Mío' })],
        assigned: [ticketSummary({ id: 2, title: 'Mío' })],
      })
      const { router } = renderQueue()
      await screen.findByText('Del resto de la cola')

      await userEvent.click(tab('Asignados a mí'))

      await waitFor(() => expect(screen.queryByText('Del resto de la cola')).not.toBeInTheDocument())
      expect(await screen.findByText('Mío')).toBeVisible()
      expect(router.state.location.search).toBe('?view=assigned')
      expect(tab('Asignados a mí')).toHaveAttribute('aria-current', 'page')

      await userEvent.click(tab('Cola'))

      expect(await screen.findByText('Del resto de la cola')).toBeVisible()
      expect(router.state.location.search).toBe('?view=queue')
      expect(tab('Cola')).toHaveAttribute('aria-current', 'page')
    })
  })

  describe('the tickets', () => {
    it('lists them in the order the API gives them', async () => {
      stubLists({
        queue: [
          ticketSummary({ id: 3, title: 'Vence primero' }),
          ticketSummary({ id: 2, title: 'Vence después' }),
          ticketSummary({ id: 1, title: 'En espera', status: 'on_hold' }),
        ],
      })

      renderQueue()

      const items = await screen.findAllByRole('listitem')
      expect(items.map((item) => within(item).getByRole('link').textContent)).toEqual([
        'Vence primero',
        'Vence después',
        'En espera',
      ])
    })

    it('shows each ticket with its status, requester, category, priority, assignee, creation date and SLA', async () => {
      stubLists({
        queue: [
          ticketSummary({
            title: 'Pantalla negra',
            status: 'in_progress',
            priority: 'critical',
            category: { id: 1, name: 'Hardware' },
            requester: { id: 2, name: 'Bruno Castillo' },
            assignee: { id: 5, name: 'Elena Vidal' },
            created_at: '2026-10-19T13:05:00Z',
            sla: { state: 'at_risk', due_at: '2026-10-19T17:00:00Z' },
          }),
        ],
      })

      renderQueue()

      const item = await screen.findByRole('listitem')
      expect(within(item).getByText('En progreso')).toBeVisible()
      expect(within(item).getByText('Bruno Castillo')).toBeVisible()
      expect(within(item).getByText('Hardware')).toBeVisible()
      expect(within(item).getByText('Crítica')).toBeVisible()
      expect(within(item).getByText('Elena Vidal')).toBeVisible()
      expect(within(item).getByText('Fecha de creación')).toBeVisible()
      expect(within(item).getByText(formatDateTime('2026-10-19T13:05:00Z'))).toBeVisible()
      expect(within(item).getByText('Por vencer')).toBeVisible()
      expect(within(item).getByText(formatDateTime('2026-10-19T17:00:00Z'))).toBeVisible()
    })

    it.each<[TicketView, string]>([
      ['queue', '/agent'],
      ['assigned', '/agent?view=assigned'],
    ])('shows how many comments each ticket of the %s view has, in words', async (view, entry) => {
      stubLists({
        [view]: [
          ticketSummary({ id: 3, title: 'Con varios', comment_count: 5 }),
          ticketSummary({ id: 2, title: 'Con uno', comment_count: 1 }),
          ticketSummary({ id: 1, title: 'Sin ninguno', comment_count: 0 }),
        ],
      })

      renderQueue(entry)

      const items = await screen.findAllByRole('listitem')
      expect(items.map((item) => within(item).getByText(/comentario/).textContent)).toEqual([
        '5 comentarios',
        '1 comentario',
        'Sin comentarios',
      ])
    })

    it('says "Sin asignar" for a ticket nobody has taken', async () => {
      stubLists({ queue: [ticketSummary({ assignee: null })] })

      renderQueue()

      expect(await screen.findByText('Sin asignar')).toBeVisible()
    })

    it('shows a ticket on hold as paused, with no due date', async () => {
      stubLists({ queue: [ticketSummary({ status: 'on_hold', sla: { state: 'paused', due_at: null } })] })

      renderQueue()

      const item = await screen.findByRole('listitem')
      expect(within(item).getByText('En espera')).toBeVisible()
      expect(within(item).getByText('En pausa')).toBeVisible()
      expect(within(item).queryByText(/Vencimiento/)).not.toBeInTheDocument()
    })

    it('shows whether a resolved ticket met its SLA', async () => {
      stubLists({
        queue: [
          ticketSummary({ id: 1, status: 'resolved', sla: { state: 'met', due_at: '2026-10-20T13:05:00Z' } }),
          ticketSummary({ id: 2, status: 'resolved', sla: { state: 'missed', due_at: '2026-10-19T13:05:00Z' } }),
        ],
      })

      renderQueue()

      const [met, missed] = await screen.findAllByRole('listitem')
      expect(within(met).getByText('Cumplido')).toBeVisible()
      expect(within(missed).getByText('Incumplido')).toBeVisible()
    })

    it('opens a ticket from its title', async () => {
      stubApi({
        [TICKETS]: () => jsonResponse([ticketSummary({ id: 42 })]),
        [DETAIL]: () => jsonResponse(ticketDetail({ allowed_actions: [] })),
      })
      const { router } = renderQueue()

      await userEvent.click(await screen.findByRole('link', { name: 'No puedo entrar a la VPN' }))

      expect(await screen.findByText('Ticket #42')).toBeVisible()
      expect(router.state.location.pathname).toBe('/tickets/42')
    })
  })

  describe.each([
    [
      'the queue',
      '/agent',
      'Bip-bup: cargando la cola...',
      'Bip-bup: la cola está despejada',
      /no pude cargar la cola/,
    ],
    [
      'the assigned tickets',
      '/agent?view=assigned',
      'Bip-bup: cargando tus tickets asignados...',
      'Bip-bup: no tienes tickets asignados',
      /no pude cargar tus tickets asignados/,
    ],
  ])('%s', (_name, entry, loading, empty, failure) => {
    it('says it is loading until the tickets arrive', async () => {
      stubLists({})

      renderQueue(entry)

      expect(screen.getByRole('status')).toHaveTextContent(loading)
      await screen.findByText(empty)
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
    })

    it('tells the agent there is nothing to do when there are no tickets', async () => {
      stubLists({})

      renderQueue(entry)

      expect(await screen.findByText(empty)).toBeVisible()
      expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
    })

    it('shows a generic message when loading fails for an unknown reason', async () => {
      stubApi({ [TICKETS]: () => jsonResponse({ detail: 'boom' }, 500) })

      renderQueue(entry)

      expect(await screen.findByRole('alert')).toHaveTextContent(failure)
      expect(screen.queryByText(empty)).not.toBeInTheDocument()
    })

    it('keeps the tabs available when loading fails', async () => {
      stubApi({ [TICKETS]: () => jsonResponse({ detail: 'boom' }, 500) })

      renderQueue(entry)
      await screen.findByRole('alert')

      expect(tab('Cola')).toBeVisible()
      expect(tab('Asignados a mí')).toBeVisible()
    })
  })

  it('shows the message of the API when it explains the failure', async () => {
    stubApi({ [TICKETS]: () => jsonResponse({ code: 'forbidden', message: 'No puedes ver esta vista.' }, 403) })

    renderQueue()

    expect(await screen.findByRole('alert')).toHaveTextContent('No puedes ver esta vista.')
  })

  describe('the filters and the sort order', () => {
    const critical = ticketSummary({ id: 1, title: 'Crítico', priority: 'critical' })
    const low = ticketSummary({ id: 2, title: 'Menor', priority: 'low' })
    const high = ticketSummary({ id: 3, title: 'Importante', priority: 'high' })

    async function shownTitles() {
      const items = await screen.findAllByRole('listitem')
      return items.map((item) => within(item).getByRole('link').textContent)
    }

    it.each<[TicketView, string]>([
      ['queue', '/agent?priority=critical'],
      ['assigned', '/agent?view=assigned&priority=critical'],
    ])('apply to the tickets of the %s view, from the address', async (view, entry) => {
      stubLists({ [view]: [low, critical, high] })

      renderQueue(entry)

      expect(await shownTitles()).toEqual(['Crítico'])
      expect(screen.getByLabelText('Prioridad')).toHaveDisplayValue('Crítica')
      expect(screen.getByText('Mostrando 1 de 3 tickets')).toBeVisible()
    })

    it('combine with the view: changing a control keeps "view" in the address', async () => {
      stubLists({ assigned: [low, critical, high] })
      const { router } = renderQueue('/agent?view=assigned&priority=critical')
      await screen.findAllByRole('listitem')

      await userEvent.selectOptions(screen.getByLabelText('Ordenar por'), 'Prioridad')

      expect(router.state.location.search).toBe('?view=assigned&priority=critical&sort=priority')
      expect(tab('Asignados a mí')).toHaveAttribute('aria-current', 'page')
    })

    it('keeps the order of the API when no sort order is chosen, and uses the chosen one otherwise', async () => {
      stubLists({ queue: [low, critical, high] })
      renderQueue()
      expect(await shownTitles()).toEqual(['Menor', 'Crítico', 'Importante'])

      await userEvent.selectOptions(screen.getByLabelText('Ordenar por'), 'Prioridad')
      expect(await shownTitles()).toEqual(['Crítico', 'Importante', 'Menor'])

      await userEvent.selectOptions(screen.getByLabelText('Ordenar por'), 'Predeterminado')
      expect(await shownTitles()).toEqual(['Menor', 'Crítico', 'Importante'])
    })

    it('stay as they are when the agent switches tab, and apply to the tickets of the new view', async () => {
      stubLists({ queue: [low, critical], assigned: [high, critical, low] })
      const { router } = renderQueue('/agent?priority=critical&sort=due')
      expect(await screen.findByText('Mostrando 1 de 2 tickets')).toBeVisible()

      await userEvent.click(tab('Asignados a mí'))

      expect(await screen.findByText('Mostrando 1 de 3 tickets')).toBeVisible()
      expect(await shownTitles()).toEqual(['Crítico'])
      expect(router.state.location.search).toBe('?priority=critical&sort=due&view=assigned')
      expect(screen.getByLabelText('Prioridad')).toHaveDisplayValue('Crítica')
      expect(screen.getByLabelText('Ordenar por')).toHaveDisplayValue('Vencimiento')
      expect(tab('Asignados a mí')).toHaveAttribute('aria-current', 'page')
    })

    it('are not offered when the view is empty, which keeps its own message', async () => {
      stubLists({})

      renderQueue('/agent?view=assigned&priority=critical')

      expect(await screen.findByText('Bip-bup: no tienes tickets asignados')).toBeVisible()
      expect(screen.queryByLabelText('Prioridad')).not.toBeInTheDocument()
    })

    it('say apart from the empty view that the filters left nothing', async () => {
      stubLists({ queue: [low, high] })

      renderQueue('/agent?priority=critical')

      expect(await screen.findByText('Bip-bup: ningún ticket coincide con los filtros')).toBeVisible()
      expect(screen.queryByText('Bip-bup: la cola está despejada')).not.toBeInTheDocument()
    })
  })

  describe('taking a ticket from its detail', () => {
    const ELENA = { id: agentElena.id, name: agentElena.name }
    const MARTA = { id: 6, name: 'Marta Soto' }
    const open = ticketDetail({ allowed_actions: ['take', 'comment'] })

    function taken(by: { id: number; name: string }, allowedActions: TicketDetail['allowed_actions']) {
      return ticketDetail({ status: 'in_progress', assignee: by, allowed_actions: allowedActions })
    }

    function stubTicket(handlers: { detail: () => TicketDetail; transition: () => Response }) {
      return stubApi({
        [TICKETS]: (request) => {
          const ticket = handlers.detail()
          const mine = ticket.assignee?.id === agentElena.id
          return jsonResponse(viewOf(request) === 'assigned' && !mine ? [] : [ticket])
        },
        [DETAIL]: () => jsonResponse(handlers.detail()),
        [TRANSITION]: handlers.transition,
      })
    }

    it('stays on the ticket in progress, and the queue and the assigned tickets show it taken', async () => {
      let current = open
      const fetchMock = stubTicket({
        detail: () => current,
        transition: () => {
          current = taken(ELENA, ['hold', 'resolve', 'comment'])
          return jsonResponse(current)
        },
      })
      const { router } = renderQueue()
      await userEvent.click(await screen.findByRole('link', { name: 'No puedo entrar a la VPN' }))
      const listRequestsBefore = listRequests(fetchMock).length

      await userEvent.click(await screen.findByRole('button', { name: 'Tomar' }))

      const facts = within(await screen.findByRole('region', { name: 'Datos' }))
      expect(await facts.findByText('En progreso')).toBeVisible()
      expect(facts.getByText('Elena Vidal')).toBeVisible()
      expect(screen.getByRole('button', { name: 'Resolver' })).toBeVisible()
      expect(screen.queryByRole('button', { name: 'Tomar' })).not.toBeInTheDocument()
      expect(router.state.location.pathname).toBe('/tickets/42')
      await waitFor(() => expect(listRequests(fetchMock).length).toBeGreaterThan(listRequestsBefore))

      await userEvent.click(screen.getByRole('link', { name: 'Volver a la cola' }))
      const queued = await screen.findByRole('listitem')
      expect(within(queued).getByText('En progreso')).toBeVisible()
      expect(within(queued).getByText('Elena Vidal')).toBeVisible()

      await userEvent.click(tab('Asignados a mí'))
      expect(within(await screen.findByRole('listitem')).getByText('No puedo entrar a la VPN')).toBeVisible()
    })

    it('tells the agent somebody else was first, and brings the page and the queue up to date', async () => {
      let current = open
      const fetchMock = stubTicket({
        detail: () => current,
        transition: () => {
          current = taken(MARTA, ['comment'])
          return jsonResponse({ code: 'already_taken', message: 'Este ticket ya fue tomado por otro agente.' }, 409)
        },
      })
      renderQueue()
      await userEvent.click(await screen.findByRole('link', { name: 'No puedo entrar a la VPN' }))
      const listRequestsBefore = listRequests(fetchMock).length

      await userEvent.click(await screen.findByRole('button', { name: 'Tomar' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('Este ticket ya fue tomado por otro agente.')
      await waitFor(() => expect(screen.queryByRole('button', { name: 'Tomar' })).not.toBeInTheDocument())
      const facts = within(screen.getByRole('region', { name: 'Datos' }))
      expect(facts.getByText('En progreso')).toBeVisible()
      expect(facts.getByText('Marta Soto')).toBeVisible()
      await waitFor(() => expect(listRequests(fetchMock).length).toBeGreaterThan(listRequestsBefore))

      await userEvent.click(screen.getByRole('link', { name: 'Volver a la cola' }))
      expect(within(await screen.findByRole('listitem')).getByText('Marta Soto')).toBeVisible()
    })
  })
})
