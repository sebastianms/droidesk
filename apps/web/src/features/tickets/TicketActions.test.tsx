import type { QueryClient } from '@tanstack/react-query'
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { $api } from '../../api/client'
import { slaPolicies, ticketDetail } from '../../test/fixtures'
import { agentElena, jsonResponse, renderRoutes, requesterAna, signInAs, stubApi } from '../../test/helpers'
import { ACTION_LABEL } from './labels'
import { TicketActions } from './TicketActions'
import type { TicketAction, TicketDetail, TicketView, TransitionAction } from './types'

const TRANSITION = 'POST /api/v1/tickets/42/transitions'
const PATCH = 'PATCH /api/v1/tickets/42'
const POLICIES = 'GET /api/v1/sla-policies'
const LIST = 'GET /api/v1/tickets'
const DETAIL_KEY = ['get', '/api/v1/tickets/{ticket_id}', { params: { path: { ticket_id: 42 } } }]
const EVERY_VIEW: TicketView[] = ['queue', 'assigned', 'mine']

function renderActions(ticket: TicketDetail, user = requesterAna) {
  signInAs(user)
  return renderRoutes([{ path: '/', element: <TicketActions ticket={ticket} /> }], '/')
}

/** Deja en caché los tres listados, como si el usuario ya los hubiera abierto antes de entrar al ticket. */
async function cacheEveryList(queryClient: QueryClient) {
  for (const view of EVERY_VIEW) {
    await queryClient.prefetchQuery($api.queryOptions('get', '/api/v1/tickets', { params: { query: { view } } }))
  }
}

function requestedViews(fetchMock: ReturnType<typeof stubApi>) {
  return fetchMock.mock.calls
    .map(([request]) => request)
    .filter((request) => request.method === 'GET')
    .map((request) => new URL(request.url).searchParams.get('view'))
    .sort()
}

function ticketAllowing(...actions: TicketAction[]) {
  return ticketDetail({ allowed_actions: actions })
}

function buttonNames() {
  return screen.queryAllByRole('button').map((button) => button.textContent)
}

/** Los botones de las transiciones: el ajuste de prioridad es otro control, con su propio botón. */
function transitionNames() {
  return buttonNames().filter((name) => name !== ACTION_LABEL.change_priority)
}

function sentActions(fetchMock: ReturnType<typeof stubApi>) {
  return Promise.all(
    fetchMock.mock.calls
      .map(([request]) => request)
      .filter((request) => request.method === 'POST')
      .map(async (request) => (await request.json()).action),
  )
}

describe('TicketActions', () => {
  // Los tickets que permiten ajustar la prioridad piden las políticas de SLA para ofrecerlas.
  beforeEach(() => {
    stubApi({ [POLICIES]: () => jsonResponse(slaPolicies) })
  })

  describe('buttons', () => {
    it.each<[TicketAction, string]>([
      ['take', 'Tomar'],
      ['cancel', 'Cancelar'],
      ['hold', 'Dejar en espera'],
      ['resume', 'Retomar'],
      ['resolve', 'Resolver'],
      ['close', 'Confirmar cierre'],
      ['reopen', 'Reabrir'],
    ])('offers %s as a button when the API allows it', (action, label) => {
      renderActions(ticketAllowing(action))

      expect(screen.getByRole('button', { name: label })).toBeEnabled()
    })

    it('offers exactly the actions the API allows, in its order', () => {
      renderActions(ticketAllowing('resolve', 'hold'))

      expect(buttonNames()).toEqual(['Resolver', 'Dejar en espera'])
    })

    describe.each<[string, TicketAction[], string[], string | null]>([
      ['an agent looking at an open ticket', ['take', 'comment', 'change_priority'], ['Tomar'], 'Tomar'],
      [
        'the agent working on a ticket',
        ['hold', 'resolve', 'comment', 'change_priority'],
        ['Dejar en espera', 'Resolver'],
        'Resolver',
      ],
      ['the agent with the ticket on hold', ['resume', 'comment', 'change_priority'], ['Retomar'], 'Retomar'],
      [
        'the requester of a resolved ticket',
        ['close', 'reopen', 'comment'],
        ['Confirmar cierre', 'Reabrir'],
        'Confirmar cierre',
      ],
      ['the requester of an open ticket', ['cancel', 'comment'], ['Cancelar'], null],
    ])('for %s', (_who, allowed, names, mainAction) => {
      it('offers only the transitions the API allows', () => {
        renderActions(ticketAllowing(...allowed))

        expect(transitionNames()).toEqual(names)
      })

      it('highlights the main action and leaves the others as secondary', () => {
        renderActions(ticketAllowing(...allowed))

        const main = screen.queryAllByRole('button').filter((button) => /primary/.test(button.className))
        expect(main.map((button) => button.textContent)).toEqual(mainAction ? [mainAction] : [])
      })
    })

    it('does not offer what the API does not allow', () => {
      renderActions(ticketAllowing('cancel'))

      expect(buttonNames()).toEqual(['Cancelar'])
    })

    it('does not make a transition button out of comment', () => {
      renderActions(ticketAllowing('cancel', 'comment'))

      expect(buttonNames()).toEqual(['Cancelar'])
    })

    it.each([
      ['no actions', []],
      ['only comment, which has its own box', ['comment']],
    ] as [string, TicketAction[]][])('shows nothing at all with %s', (_case, actions) => {
      renderActions(ticketAllowing(...actions))

      expect(screen.queryByRole('region', { name: 'Acciones' })).not.toBeInTheDocument()
      expect(buttonNames()).toEqual([])
    })
  })

  describe('a transition', () => {
    it('asks the API for the action and keeps the ticket it answers with', async () => {
      const updated = ticketDetail({ status: 'resolved', allowed_actions: ['close', 'reopen'] })
      const fetchMock = stubApi({ [TRANSITION]: () => jsonResponse(updated) })
      const { queryClient } = renderActions(ticketAllowing('resolve'))

      await userEvent.click(screen.getByRole('button', { name: 'Resolver' }))

      await waitFor(() => expect(queryClient.getQueryData(DETAIL_KEY)).toEqual(updated))
      expect(await sentActions(fetchMock)).toEqual(['resolve'])
    })

    it.each<TransitionAction>(['take', 'hold', 'resume', 'resolve', 'close', 'reopen'])(
      'applies %s right away, with no confirmation',
      async (action) => {
        const fetchMock = stubApi({ [TRANSITION]: () => jsonResponse(ticketDetail()) })
        renderActions(ticketAllowing(action))

        await userEvent.click(screen.getByRole('button', { name: ACTION_LABEL[action] }))

        await waitFor(() => expect(fetchMock).toHaveBeenCalled())
        expect(await sentActions(fetchMock)).toEqual([action])
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      },
    )

    it('refreshes the queue, the assigned tickets and "Mis tickets", which show the old status', async () => {
      const fetchMock = stubApi({
        [LIST]: () => jsonResponse([]),
        [TRANSITION]: () => jsonResponse(ticketDetail({ status: 'in_progress' })),
      })
      const { queryClient } = renderActions(ticketAllowing('take'), agentElena)
      await cacheEveryList(queryClient)
      fetchMock.mockClear()

      await userEvent.click(screen.getByRole('button', { name: 'Tomar' }))

      await waitFor(() => expect(requestedViews(fetchMock)).toEqual(['assigned', 'mine', 'queue']))
    })

    it('refreshes the detail when the change is rejected, because the screen is out of date', async () => {
      stubApi({ [TRANSITION]: () => jsonResponse({ code: 'action_not_allowed', message: 'Ya no se puede.' }, 409) })
      const { queryClient } = renderActions(ticketAllowing('resolve'))
      const invalidate = vi.spyOn(queryClient, 'invalidateQueries')

      await userEvent.click(screen.getByRole('button', { name: 'Resolver' }))

      await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: DETAIL_KEY }))
    })

    it('refreshes the lists too when the change is rejected, because they are out of date as well', async () => {
      const fetchMock = stubApi({
        [LIST]: () => jsonResponse([]),
        [TRANSITION]: () => jsonResponse({ code: 'already_taken', message: 'Ya lo tomó otro.' }, 409),
      })
      const { queryClient } = renderActions(ticketAllowing('take'), agentElena)
      await cacheEveryList(queryClient)
      fetchMock.mockClear()

      await userEvent.click(screen.getByRole('button', { name: 'Tomar' }))

      await waitFor(() => expect(requestedViews(fetchMock)).toEqual(['assigned', 'mine', 'queue']))
    })

    it('blocks the buttons while the change is in flight', async () => {
      let finish: (response: Response) => void = () => {}
      stubApi({ [TRANSITION]: () => new Promise<Response>((resolve) => (finish = resolve)) })
      renderActions(ticketAllowing('hold', 'resolve'))

      await userEvent.click(screen.getByRole('button', { name: 'Resolver' }))

      expect(screen.getByRole('button', { name: 'Resolver' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'Dejar en espera' })).toBeDisabled()
      finish(jsonResponse(ticketDetail()))
      await waitFor(() => expect(screen.getByRole('button', { name: 'Resolver' })).toBeEnabled())
    })

    it('shows the explanation of the API when the change is no longer possible', async () => {
      stubApi({
        [TRANSITION]: () => jsonResponse({ code: 'action_not_allowed', message: 'El ticket ya fue tomado.' }, 409),
      })
      renderActions(ticketAllowing('cancel'))

      await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
      await userEvent.click(screen.getByRole('button', { name: 'Sí, cancelar ticket' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('El ticket ya fue tomado.')
      expect(screen.getByRole('button', { name: 'Cancelar' })).toBeEnabled()
    })

    it('tells the agent that another agent took the ticket first, in the words of the API', async () => {
      stubApi({
        [TRANSITION]: () =>
          jsonResponse({ code: 'already_taken', message: 'Este ticket ya fue tomado por otro agente.' }, 409),
      })
      renderActions(ticketAllowing('take'), agentElena)

      await userEvent.click(screen.getByRole('button', { name: 'Tomar' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('Este ticket ya fue tomado por otro agente.')
    })

    it('shows a generic message when the failure has no explanation', async () => {
      stubApi({ [TRANSITION]: () => jsonResponse({ detail: 'boom' }, 500) })
      renderActions(ticketAllowing('resolve'))

      await userEvent.click(screen.getByRole('button', { name: 'Resolver' }))

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Bip-bup: no pude aplicar el cambio. Intenta de nuevo.',
      )
    })

    it('clears the failure when the next attempt goes through', async () => {
      let attempts = 0
      stubApi({
        [TRANSITION]: () => (++attempts === 1 ? jsonResponse({ detail: 'boom' }, 500) : jsonResponse(ticketDetail())),
      })
      renderActions(ticketAllowing('resolve'))
      await userEvent.click(screen.getByRole('button', { name: 'Resolver' }))
      await screen.findByRole('alert')

      await userEvent.click(screen.getByRole('button', { name: 'Resolver' }))

      await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    })
  })

  describe('changing the priority', () => {
    const highPriority = () => ticketDetail({ priority: 'high', allowed_actions: ['comment', 'change_priority'] })

    function sentPriorities(fetchMock: ReturnType<typeof stubApi>) {
      return Promise.all(
        fetchMock.mock.calls
          .map(([request]) => request)
          .filter((request) => request.method === 'PATCH')
          .map(async (request) => (await request.json()).priority),
      )
    }

    function stubPriorityApi(handlers: Parameters<typeof stubApi>[0] = {}) {
      return stubApi({ [POLICIES]: () => jsonResponse(slaPolicies), ...handlers })
    }

    async function pick(label: string) {
      await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'Prioridad' }), label)
    }

    it('offers the control, alone in the panel, when the API allows changing the priority', async () => {
      renderActions(ticketAllowing('comment', 'change_priority'), agentElena)

      const panel = within(screen.getByRole('region', { name: 'Acciones' }))
      expect(await panel.findByRole('combobox', { name: 'Prioridad' })).toBeVisible()
      expect(panel.getByRole('button', { name: 'Cambiar prioridad' })).toBeVisible()
      expect(buttonNames()).toEqual(['Cambiar prioridad'])
    })

    it('does not offer it, nor ask for the priorities, when the API does not allow it', () => {
      const fetchMock = stubPriorityApi()
      renderActions(ticketAllowing('resolve', 'comment'), agentElena)

      expect(screen.queryByRole('combobox', { name: 'Prioridad' })).not.toBeInTheDocument()
      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('offers every priority with the deadline it commits to', async () => {
      renderActions(highPriority(), agentElena)

      await screen.findByRole('combobox', { name: 'Prioridad' })

      expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual([
        'Crítica · 4 horas hábiles',
        'Alta · 1 día hábil',
        'Media · 3 días hábiles',
        'Baja · 5 días hábiles',
      ])
    })

    it('starts on the current priority, with nothing to change yet', async () => {
      renderActions(highPriority(), agentElena)

      expect(await screen.findByRole('combobox', { name: 'Prioridad' })).toHaveValue('high')
      expect(screen.getByRole('button', { name: 'Cambiar prioridad' })).toBeDisabled()
    })

    it('enables the change only while the picked priority differs from the current one', async () => {
      renderActions(highPriority(), agentElena)

      await pick('Baja · 5 días hábiles')
      expect(screen.getByRole('button', { name: 'Cambiar prioridad' })).toBeEnabled()

      await pick('Alta · 1 día hábil')
      expect(screen.getByRole('button', { name: 'Cambiar prioridad' })).toBeDisabled()
    })

    it('asks the API for the picked priority and keeps the ticket it answers with', async () => {
      const updated = ticketDetail({ priority: 'low', allowed_actions: ['comment', 'change_priority'] })
      const fetchMock = stubPriorityApi({ [PATCH]: () => jsonResponse(updated) })
      const { queryClient } = renderActions(highPriority(), agentElena)
      await pick('Baja · 5 días hábiles')

      await userEvent.click(screen.getByRole('button', { name: 'Cambiar prioridad' }))

      await waitFor(() => expect(queryClient.getQueryData(DETAIL_KEY)).toEqual(updated))
      expect(await sentPriorities(fetchMock)).toEqual(['low'])
    })

    it('refreshes the queue, the assigned tickets and "Mis tickets", which show the old priority and order', async () => {
      const fetchMock = stubPriorityApi({
        [LIST]: () => jsonResponse([]),
        [PATCH]: () => jsonResponse(ticketDetail({ priority: 'low' })),
      })
      const { queryClient } = renderActions(highPriority(), agentElena)
      await cacheEveryList(queryClient)
      fetchMock.mockClear()
      await pick('Baja · 5 días hábiles')

      await userEvent.click(screen.getByRole('button', { name: 'Cambiar prioridad' }))

      await waitFor(() => expect(requestedViews(fetchMock)).toEqual(['assigned', 'mine', 'queue']))
    })

    it('blocks the change while it is in flight', async () => {
      let finish: (response: Response) => void = () => {}
      stubPriorityApi({ [PATCH]: () => new Promise<Response>((resolve) => (finish = resolve)) })
      const { queryClient } = renderActions(highPriority(), agentElena)
      await pick('Baja · 5 días hábiles')
      expect(screen.getByRole('button', { name: 'Cambiar prioridad' })).toBeEnabled()

      await userEvent.click(screen.getByRole('button', { name: 'Cambiar prioridad' }))

      expect(screen.getByRole('button', { name: 'Cambiar prioridad' })).toBeDisabled()
      const updated = ticketDetail({ priority: 'low' })
      finish(jsonResponse(updated))
      await waitFor(() => expect(queryClient.getQueryData(DETAIL_KEY)).toEqual(updated))
    })

    it('shows the explanation of the API when the ticket changed in the meantime, and brings the screen up to date', async () => {
      const fetchMock = stubPriorityApi({
        [LIST]: () => jsonResponse([]),
        [PATCH]: () =>
          jsonResponse(
            { code: 'action_not_allowed', message: 'El ticket cambió mientras ajustabas su prioridad.' },
            409,
          ),
      })
      const { queryClient } = renderActions(highPriority(), agentElena)
      await cacheEveryList(queryClient)
      const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
      fetchMock.mockClear()
      await pick('Baja · 5 días hábiles')

      await userEvent.click(screen.getByRole('button', { name: 'Cambiar prioridad' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('El ticket cambió mientras ajustabas su prioridad.')
      expect(invalidate).toHaveBeenCalledWith({ queryKey: DETAIL_KEY })
      await waitFor(() => expect(requestedViews(fetchMock)).toEqual(['assigned', 'mine', 'queue']))
    })

    it('lets the agent try again after a rejection, keeping the priority they picked', async () => {
      stubPriorityApi({
        [PATCH]: () => jsonResponse({ code: 'action_not_allowed', message: 'El ticket cambió.' }, 409),
      })
      renderActions(highPriority(), agentElena)
      await pick('Baja · 5 días hábiles')
      await userEvent.click(screen.getByRole('button', { name: 'Cambiar prioridad' }))
      await screen.findByRole('alert')

      expect(screen.getByRole('combobox', { name: 'Prioridad' })).toHaveValue('low')
      expect(screen.getByRole('button', { name: 'Cambiar prioridad' })).toBeEnabled()
    })

    it('shows a generic message when the failure has no explanation', async () => {
      stubPriorityApi({ [PATCH]: () => jsonResponse({ detail: 'boom' }, 500) })
      renderActions(highPriority(), agentElena)
      await pick('Baja · 5 días hábiles')

      await userEvent.click(screen.getByRole('button', { name: 'Cambiar prioridad' }))

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Bip-bup: no pude cambiar la prioridad. Intenta de nuevo.',
      )
    })

    it('clears the failure when the next attempt goes through', async () => {
      let attempts = 0
      stubPriorityApi({
        [PATCH]: () => (++attempts === 1 ? jsonResponse({ detail: 'boom' }, 500) : jsonResponse(ticketDetail())),
      })
      renderActions(highPriority(), agentElena)
      await pick('Baja · 5 días hábiles')
      await userEvent.click(screen.getByRole('button', { name: 'Cambiar prioridad' }))
      await screen.findByRole('alert')

      await userEvent.click(screen.getByRole('button', { name: 'Cambiar prioridad' }))

      await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    })

    it('says it is loading the priorities until they arrive', () => {
      stubApi({ [POLICIES]: () => new Promise<Response>(() => {}) })
      renderActions(highPriority(), agentElena)

      expect(screen.getByRole('status')).toHaveTextContent('Bip-bup: cargando las prioridades...')
    })

    it('says it could not load the priorities, without offering to change anything', async () => {
      stubApi({ [POLICIES]: () => jsonResponse({ detail: 'boom' }, 500) })
      renderActions(highPriority(), agentElena)

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Bip-bup: no pude cargar las prioridades. Intenta de nuevo.',
      )
      expect(screen.queryByRole('button', { name: 'Cambiar prioridad' })).not.toBeInTheDocument()
    })

    it('shows the message of the API when it explains why the priorities did not load', async () => {
      stubApi({ [POLICIES]: () => jsonResponse({ code: 'forbidden', message: 'No puedes ver las prioridades.' }, 403) })
      renderActions(highPriority(), agentElena)

      expect(await screen.findByRole('alert')).toHaveTextContent('No puedes ver las prioridades.')
    })
  })

  describe('cancelling', () => {
    it('asks for confirmation before cancelling, and sends nothing yet', async () => {
      const fetchMock = stubApi({ [TRANSITION]: () => jsonResponse(ticketDetail()) })
      renderActions(ticketAllowing('cancel'))

      await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

      const dialog = screen.getByRole('dialog', { name: 'Cancelar ticket' })
      expect(dialog).toHaveAccessibleDescription(/no se puede deshacer/)
      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('cancels once the requester confirms', async () => {
      const cancelled = ticketDetail({ status: 'cancelled', allowed_actions: [] })
      const fetchMock = stubApi({ [TRANSITION]: () => jsonResponse(cancelled) })
      const { queryClient } = renderActions(ticketAllowing('cancel'))
      await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

      await userEvent.click(screen.getByRole('button', { name: 'Sí, cancelar ticket' }))

      await waitFor(() => expect(queryClient.getQueryData(DETAIL_KEY)).toEqual(cancelled))
      expect(await sentActions(fetchMock)).toEqual(['cancel'])
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('keeps the ticket when the requester changes their mind', async () => {
      const fetchMock = stubApi({ [TRANSITION]: () => jsonResponse(ticketDetail()) })
      renderActions(ticketAllowing('cancel'))
      await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

      await userEvent.click(screen.getByRole('button', { name: 'No, volver' }))

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('keeps the ticket when the dialog is dismissed with Escape', async () => {
      const fetchMock = stubApi({ [TRANSITION]: () => jsonResponse(ticketDetail()) })
      renderActions(ticketAllowing('cancel'))
      await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

      fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }))

      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('does not ask for confirmation to take another action', async () => {
      stubApi({ [TRANSITION]: () => jsonResponse(ticketDetail()) })
      renderActions(ticketAllowing('cancel', 'hold'))

      await userEvent.click(screen.getByRole('button', { name: 'Dejar en espera' }))

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })
})
