import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ticketSummary } from '../../test/fixtures'
import { agentElena, jsonResponse, renderRoutes, signInAs, stubApi } from '../../test/helpers'
import type { Priority, SlaState, TicketSummary } from '../tickets/types'
import { QueuePage } from './QueuePage'

const TICKETS = 'GET /api/v1/tickets'
const NO_MATCH = 'Bip-bup: ningún ticket coincide con los filtros'

const EMPTY_QUEUE = 'Bip-bup: la cola está despejada'

function renderList(tickets: TicketSummary[], entry = '/agent') {
  signInAs(agentElena)
  const fetchMock = stubApi({ [TICKETS]: () => jsonResponse(tickets) })
  const { router } = renderRoutes([{ path: '/agent', element: <QueuePage /> }], entry)
  return { router, fetchMock }
}

function ticket(id: number, fields: { priority?: Priority; state?: SlaState | null; due?: string | null } = {}) {
  const { priority = 'medium', state = 'on_track', due = '2026-10-21T10:00:00Z' } = fields
  return ticketSummary({
    id,
    title: `Ticket ${id}`,
    priority,
    created_at: `2026-10-19T0${id}:00:00Z`,
    sla: { state, due_at: due },
  })
}

// Críticos: 1 y 4; 3 sin vencimiento (en pausa). Por fecha de creación, el 4 es el más reciente.
const TICKETS_TO_FILTER = [
  ticket(1, { priority: 'critical', state: 'breached', due: '2026-10-22T10:00:00Z' }),
  ticket(2, { priority: 'low', state: 'at_risk', due: '2026-10-20T10:00:00Z' }),
  ticket(3, { priority: 'high', state: 'paused', due: null }),
  ticket(4, { priority: 'critical', state: 'on_track', due: '2026-10-21T10:00:00Z' }),
]

function control(label: string) {
  return screen.getByLabelText(label)
}

async function choose(label: string, option: string) {
  await userEvent.selectOptions(control(label), option)
}

async function shownTitles() {
  const items = await screen.findAllByRole('listitem')
  return items.map((item) => within(item).getByRole('link').textContent)
}

function titles(...ids: number[]) {
  return ids.map((id) => `Ticket ${id}`)
}

describe('the filters and the sort order of a listing', () => {
  describe('the controls', () => {
    it('are labelled and start on their default option', async () => {
      renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')

      expect(control('Prioridad')).toHaveDisplayValue('Todas')
      expect(control('SLA')).toHaveDisplayValue('Todos')
      expect(control('Ordenar por')).toHaveDisplayValue('Predeterminado')
    })

    it('offer the priorities from critical to low', async () => {
      renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')

      const options = within(control('Prioridad')).getAllByRole('option')
      expect(options.map((option) => option.textContent)).toEqual(['Todas', 'Crítica', 'Alta', 'Media', 'Baja'])
    })

    it('offer every SLA state', async () => {
      renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')

      const options = within(control('SLA')).getAllByRole('option')
      expect(options.map((option) => option.textContent)).toEqual([
        'Todos',
        'Vencido',
        'Por vencer',
        'En plazo',
        'En pausa',
        'Cumplido',
        'Incumplido',
      ])
    })

    it('offer the three ways to sort next to the default order', async () => {
      renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')

      const options = within(control('Ordenar por')).getAllByRole('option')
      expect(options.map((option) => option.textContent)).toEqual([
        'Predeterminado',
        'Vencimiento',
        'Prioridad',
        'Más recientes',
      ])
    })

    it('show neither a count nor a button to clear while nothing is chosen', async () => {
      renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')

      expect(screen.queryByText(/Mostrando/)).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Limpiar filtros' })).not.toBeInTheDocument()
    })

    it('are not shown while loading or when loading fails', async () => {
      signInAs(agentElena)
      stubApi({ [TICKETS]: () => jsonResponse({ detail: 'boom' }, 500) })
      renderRoutes([{ path: '/agent', element: <QueuePage /> }], '/agent')

      expect(screen.queryByLabelText('Prioridad')).not.toBeInTheDocument()
      await screen.findByRole('alert')
      expect(screen.queryByLabelText('Prioridad')).not.toBeInTheDocument()
    })

    it('are not shown when the view has no tickets', async () => {
      renderList([])

      expect(await screen.findByText(EMPTY_QUEUE)).toBeVisible()
      expect(screen.queryByLabelText('Prioridad')).not.toBeInTheDocument()
    })
  })

  describe('without a choice', () => {
    it('keeps the order in which the API gives the tickets', async () => {
      renderList(TICKETS_TO_FILTER)

      expect(await shownTitles()).toEqual(titles(1, 2, 3, 4))
    })

    it('does not ask the API for anything different, because it filters in the browser', async () => {
      const { fetchMock } = renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')

      await choose('Prioridad', 'Crítica')
      await choose('SLA', 'Vencido')
      await choose('Ordenar por', 'Prioridad')

      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(new URL(fetchMock.mock.calls[0][0].url).search).toBe('?view=queue')
    })
  })

  describe('filtering by priority', () => {
    it('keeps only that priority, says how many are shown and writes the choice in the address', async () => {
      const { router } = renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')

      await choose('Prioridad', 'Crítica')

      expect(await shownTitles()).toEqual(titles(1, 4))
      expect(screen.getByText('Mostrando 2 de 4 tickets')).toBeVisible()
      expect(router.state.location.search).toBe('?priority=critical')
    })

    it('goes back to every priority with "Todas", which takes the choice out of the address', async () => {
      const { router } = renderList(TICKETS_TO_FILTER, '/agent?priority=low')
      expect(await shownTitles()).toEqual(titles(2))

      await choose('Prioridad', 'Todas')

      expect(await shownTitles()).toEqual(titles(1, 2, 3, 4))
      expect(router.state.location.search).toBe('')
      expect(screen.queryByText(/Mostrando/)).not.toBeInTheDocument()
    })
  })

  describe('filtering by SLA state', () => {
    it('keeps only that state and writes the choice in the address', async () => {
      const { router } = renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')

      await choose('SLA', 'En pausa')

      expect(await shownTitles()).toEqual(titles(3))
      expect(screen.getByText('Mostrando 1 de 4 tickets')).toBeVisible()
      expect(router.state.location.search).toBe('?sla=paused')
    })

    it('leaves out a cancelled ticket, which has no SLA state, as soon as an SLA state is chosen', async () => {
      renderList([...TICKETS_TO_FILTER, ticket(5, { state: null, due: null })])
      expect(await shownTitles()).toEqual(titles(1, 2, 3, 4, 5))

      await choose('SLA', 'En plazo')

      expect(await shownTitles()).toEqual(titles(4))
    })
  })

  it('combines the priority and the SLA state', async () => {
    const { router } = renderList(TICKETS_TO_FILTER)
    await screen.findAllByRole('listitem')

    await choose('Prioridad', 'Crítica')
    await choose('SLA', 'Vencido')

    expect(await shownTitles()).toEqual(titles(1))
    expect(screen.getByText('Mostrando 1 de 4 tickets')).toBeVisible()
    expect(router.state.location.search).toBe('?priority=critical&sla=breached')
  })

  describe('sorting', () => {
    it.each([
      ['Vencimiento', 'due', titles(2, 4, 1, 3)],
      ['Prioridad', 'priority', titles(4, 1, 3, 2)],
      ['Más recientes', 'recent', titles(4, 3, 2, 1)],
    ])('by "%s" orders the tickets and writes sort=%s in the address', async (option, sort, expected) => {
      const { router } = renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')

      await choose('Ordenar por', option)

      expect(await shownTitles()).toEqual(expected)
      expect(router.state.location.search).toBe(`?sort=${sort}`)
    })

    it('does not say "Mostrando" when it is the only thing chosen, but offers to clear it', async () => {
      renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')

      await choose('Ordenar por', 'Vencimiento')

      expect(screen.queryByText(/Mostrando/)).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Limpiar filtros' })).toBeVisible()
    })

    it('sorts only the tickets that the filters leave', async () => {
      renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')

      await choose('Prioridad', 'Crítica')
      await choose('Ordenar por', 'Vencimiento')

      expect(await shownTitles()).toEqual(titles(4, 1))
    })

    it('goes back to the order of the API with "Predeterminado"', async () => {
      const { router } = renderList(TICKETS_TO_FILTER, '/agent?sort=recent')
      expect(await shownTitles()).toEqual(titles(4, 3, 2, 1))

      await choose('Ordenar por', 'Predeterminado')

      expect(await shownTitles()).toEqual(titles(1, 2, 3, 4))
      expect(router.state.location.search).toBe('')
    })
  })

  describe('the address', () => {
    it('sets the controls and the list when it is opened with filters', async () => {
      renderList(TICKETS_TO_FILTER, '/agent?priority=critical&sla=on_track&sort=due')

      expect(await shownTitles()).toEqual(titles(4))
      expect(control('Prioridad')).toHaveDisplayValue('Crítica')
      expect(control('SLA')).toHaveDisplayValue('En plazo')
      expect(control('Ordenar por')).toHaveDisplayValue('Vencimiento')
      expect(screen.getByText('Mostrando 1 de 4 tickets')).toBeVisible()
    })

    it('ignores the values it does not know, as if nothing had been chosen', async () => {
      const { router } = renderList(TICKETS_TO_FILTER, '/agent?priority=urgent&sla=late&sort=oldest')

      expect(await shownTitles()).toEqual(titles(1, 2, 3, 4))
      expect(control('Prioridad')).toHaveDisplayValue('Todas')
      expect(control('SLA')).toHaveDisplayValue('Todos')
      expect(control('Ordenar por')).toHaveDisplayValue('Predeterminado')
      expect(screen.queryByRole('button', { name: 'Limpiar filtros' })).not.toBeInTheDocument()
      expect(router.state.location.search).toBe('?priority=urgent&sla=late&sort=oldest')
    })

    it('keeps the other parameters, like the view, when a control changes', async () => {
      const { router } = renderList(TICKETS_TO_FILTER, '/agent?view=assigned&sla=at_risk')
      await screen.findAllByRole('listitem')

      await choose('Prioridad', 'Baja')

      expect(router.state.location.search).toBe('?view=assigned&sla=at_risk&priority=low')
    })

    it('replaces the history entry on each change, so "Atrás" does not step through them', async () => {
      const { router } = renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')

      await choose('Prioridad', 'Crítica')
      await choose('SLA', 'Vencido')

      expect(router.state.historyAction).toBe('REPLACE')
    })
  })

  describe('when no ticket matches', () => {
    it('says so with its own message, keeps the controls and counts zero', async () => {
      renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')

      await choose('Prioridad', 'Media')

      expect(await screen.findByText(NO_MATCH)).toBeVisible()
      expect(screen.queryByText(EMPTY_QUEUE)).not.toBeInTheDocument()
      expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
      expect(screen.getByText('Mostrando 0 de 4 tickets')).toBeVisible()
      expect(control('Prioridad')).toBeVisible()
    })

    it('lets the user get the tickets back by clearing the filters', async () => {
      renderList(TICKETS_TO_FILTER, '/agent?priority=medium')
      await screen.findByText(NO_MATCH)

      await userEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }))

      expect(await shownTitles()).toEqual(titles(1, 2, 3, 4))
      expect(screen.queryByText(NO_MATCH)).not.toBeInTheDocument()
    })
  })

  describe('"Limpiar filtros"', () => {
    it('is shown only while a filter or a sort order is chosen', async () => {
      renderList(TICKETS_TO_FILTER)
      await screen.findAllByRole('listitem')
      expect(screen.queryByRole('button', { name: 'Limpiar filtros' })).not.toBeInTheDocument()

      await choose('SLA', 'Vencido')
      expect(screen.getByRole('button', { name: 'Limpiar filtros' })).toBeVisible()

      await choose('SLA', 'Todos')
      expect(screen.queryByRole('button', { name: 'Limpiar filtros' })).not.toBeInTheDocument()
    })

    it('removes every choice from the address, keeps the other parameters and restores the order of the API', async () => {
      const { router } = renderList(
        TICKETS_TO_FILTER,
        '/agent?view=assigned&priority=critical&sla=on_track&sort=recent',
      )
      expect(await shownTitles()).toEqual(titles(4))

      await userEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }))

      expect(await shownTitles()).toEqual(titles(1, 2, 3, 4))
      expect(router.state.location.search).toBe('?view=assigned')
      expect(control('Prioridad')).toHaveDisplayValue('Todas')
      expect(control('SLA')).toHaveDisplayValue('Todos')
      expect(control('Ordenar por')).toHaveDisplayValue('Predeterminado')
      expect(screen.queryByText(/Mostrando/)).not.toBeInTheDocument()
    })

    it('hands the focus to the first control, because the button disappears', async () => {
      renderList(TICKETS_TO_FILTER, '/agent?sla=breached')
      await screen.findAllByRole('listitem')

      await userEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }))

      expect(control('Prioridad')).toHaveFocus()
    })
  })

  it('announces the count politely when it changes', async () => {
    renderList(TICKETS_TO_FILTER)
    await screen.findAllByRole('listitem')

    await choose('Prioridad', 'Crítica')

    expect(screen.getByText('Mostrando 2 de 4 tickets')).toHaveAttribute('aria-live', 'polite')
  })

  it('says "1 ticket" when the whole listing is a single ticket', async () => {
    renderList([ticket(1, { priority: 'critical' })], '/agent?priority=critical')

    expect(await screen.findByText('Mostrando 1 de 1 ticket')).toBeVisible()
  })
})
